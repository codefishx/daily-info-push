"""PubMed Top Journals 适配器 — 从 NEJM、Lancet、JAMA、BMJ、Cell 获取最新论文。

使用 NCBI E-utilities 两步流程：ESearch 获取 PMID 列表，EFetch 获取完整 XML 元数据。
"""

from __future__ import annotations

import os
import time
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from typing import List, Optional

import httpx

from adapters.base import BaseAdapter
from models import RawItem

_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
_PUBMED_URL = "https://pubmed.ncbi.nlm.nih.gov/"
_DEFAULT_LIMIT = 2
_DEFAULT_LOOKBACK_DAYS = 7

_JOURNALS = [
    '"N Engl J Med"[jour]',
    '"Lancet"[jour]',
    '"JAMA"[jour]',
    '"BMJ"[jour]',
    '"Cell"[jour]',
]

_JOURNAL_QUERY = "(" + " OR ".join(_JOURNALS) + ") AND hasabstract"


class PubMedAdapter(BaseAdapter):

    @property
    def name(self) -> str:
        return "PubMed Top Journals"

    def __init__(self) -> None:
        self.limit = int(os.environ.get("PUBMED_LIMIT", _DEFAULT_LIMIT))
        self.api_key: Optional[str] = os.environ.get("NCBI_API_KEY")
        self.lookback_days = int(os.environ.get("PUBMED_LOOKBACK_DAYS", _DEFAULT_LOOKBACK_DAYS))

    def _base_params(self) -> dict:
        params: dict = {"db": "pubmed", "tool": "daily-info-push"}
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def fetch(self) -> List[RawItem]:
        today = date.today()
        min_date = (today - timedelta(days=self.lookback_days)).strftime("%Y/%m/%d")
        max_date = today.strftime("%Y/%m/%d")

        with httpx.Client(timeout=self.timeout) as client:
            search_params = {
                **self._base_params(),
                "term": _JOURNAL_QUERY,
                "retmax": str(self.limit),
                "sort": "pub_date",
                "retmode": "json",
                "datetype": "pdat",
                "mindate": min_date,
                "maxdate": max_date,
            }
            resp = client.get(_ESEARCH_URL, params=search_params)
            resp.raise_for_status()
            pmids = resp.json()["esearchresult"]["idlist"]

            if not pmids:
                return []

            time.sleep(0.35)

            fetch_params = {
                **self._base_params(),
                "id": ",".join(pmids),
                "retmode": "xml",
                "rettype": "abstract",
            }
            resp = client.get(_EFETCH_URL, params=fetch_params)
            resp.raise_for_status()

        root = ET.fromstring(resp.content)
        items: List[RawItem] = []
        for art_elem in root.findall("PubmedArticle"):
            item = self._parse_article(art_elem)
            if item:
                items.append(item)
        return items

    @staticmethod
    def _get_text(elem: Optional[ET.Element]) -> str:
        if elem is None:
            return ""
        return "".join(elem.itertext()).strip()

    @classmethod
    def _parse_article(cls, art: ET.Element) -> Optional[RawItem]:
        cit = art.find("MedlineCitation")
        if cit is None:
            return None
        article = cit.find("Article")
        if article is None:
            return None

        pmid = cls._get_text(cit.find("PMID"))
        title = cls._get_text(article.find("ArticleTitle"))

        abstract_parts = []
        for at in article.findall("Abstract/AbstractText"):
            label = at.get("Label")
            text = "".join(at.itertext()).strip()
            if label:
                abstract_parts.append(f"{label}: {text}")
            else:
                abstract_parts.append(text)
        abstract = " ".join(abstract_parts)

        authors = []
        for author in article.findall("AuthorList/Author"):
            last = cls._get_text(author.find("LastName"))
            fore = cls._get_text(author.find("ForeName"))
            if last:
                authors.append(f"{fore} {last}".strip())
        first_author = authors[0] if authors else None

        doi = ""
        for eloc in article.findall("ELocationID"):
            if eloc.get("EIdType") == "doi":
                doi = (eloc.text or "").strip()
                break
        if not doi:
            for aid in art.findall("PubmedData/ArticleIdList/ArticleId"):
                if aid.get("IdType") == "doi":
                    doi = (aid.text or "").strip()
                    break

        journal_abbrev = cls._get_text(article.find("Journal/ISOAbbreviation"))

        pub_date_elem = article.find("Journal/JournalIssue/PubDate")
        year = cls._get_text(pub_date_elem.find("Year")) if pub_date_elem is not None else ""
        month = cls._get_text(pub_date_elem.find("Month")) if pub_date_elem is not None else ""
        day = cls._get_text(pub_date_elem.find("Day")) if pub_date_elem is not None else ""
        published_at = "-".join(part for part in [year, month, day] if part)

        url = f"https://doi.org/{doi}" if doi else f"{_PUBMED_URL}{pmid}/"

        tags = []
        for mesh in cit.findall("MeshHeadingList/MeshHeading/DescriptorName"):
            if mesh.get("MajorTopicYN") == "Y" and mesh.text:
                tags.append(mesh.text)

        return RawItem(
            id=f"pubmed_{pmid}",
            source_name="PubMed Top Journals",
            source_type="Paper",
            title=title,
            abstract=abstract,
            url=url,
            published_at=published_at,
            raw_metrics={"author_count": len(authors), "journal": journal_abbrev},
            tags=tags[:10],
            author_or_creator=first_author,
        )
