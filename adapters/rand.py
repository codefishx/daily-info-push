"""RAND Corporation 适配器 — 通过 Atom feed 获取最新出版物。"""

from __future__ import annotations

import hashlib
import html
import os
import re
import xml.etree.ElementTree as ET
from typing import List

import httpx

from adapters.base import BaseAdapter
from models import RawItem

_DEFAULT_LIMIT = 2
_ATOM_URL = "https://www.rand.org/pubs/new.xml"
_NS = {"atom": "http://www.w3.org/2005/Atom"}

_TYPE_MAP = {
    "research_reports": "Paper",
    "research_briefs": "Article",
    "commentary": "Article",
    "perspectives": "Article",
    "tools": "Tool",
    "conf_proceedings": "Article",
    "presentations": "Article",
    "external_publications": "Paper",
    "corporate_pubs": "Article",
}


def _strip_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", "", text)
    return html.unescape(clean).strip()


class RANDAdapter(BaseAdapter):

    @property
    def name(self) -> str:
        return "RAND"

    def __init__(self) -> None:
        self.limit = int(os.environ.get("RAND_LIMIT", _DEFAULT_LIMIT))

    def fetch(self) -> List[RawItem]:
        headers = {"User-Agent": "daily-info-push/1.0 (RAND-Adapter)"}
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            resp = client.get(_ATOM_URL, headers=headers)
            resp.raise_for_status()

        root = ET.fromstring(resp.text)
        items: List[RawItem] = []

        for entry in root.findall("atom:entry", _NS):
            if len(items) >= self.limit:
                break
            raw_item = self._parse_entry(entry)
            if raw_item:
                items.append(raw_item)
        return items

    @classmethod
    def _parse_entry(cls, entry: ET.Element) -> RawItem | None:
        title = _strip_html(entry.findtext("atom:title", "", _NS))
        if not title:
            return None

        link_el = entry.find("atom:link[@rel='alternate']", _NS)
        url = link_el.get("href", "") if link_el is not None else ""
        if not url:
            url = entry.findtext("atom:id", "", _NS)

        summary = _strip_html(entry.findtext("atom:summary", "", _NS))
        published = entry.findtext("atom:published", "", _NS)

        authors = []
        for author_el in entry.findall("atom:author", _NS):
            name = (author_el.findtext("atom:name", "", _NS)).strip()
            if name:
                authors.append(name)
        first_author = authors[0] if authors else None

        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        source_type = cls._detect_type(url)

        return RawItem(
            id=f"rand_{url_hash}",
            source_name="RAND",
            source_type=source_type,
            title=title,
            abstract=summary[:500],
            url=url,
            published_at=published,
            raw_metrics={"author_count": len(authors)},
            tags=[],
            author_or_creator=first_author,
        )

    @staticmethod
    def _detect_type(url: str) -> str:
        for key, val in _TYPE_MAP.items():
            if f"/pubs/{key}/" in url:
                return val
        return "Article"
