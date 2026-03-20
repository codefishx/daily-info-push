"""Brookings Institution 适配器 — 通过 WordPress REST API 获取最新研究文章。"""

from __future__ import annotations

import html
import os
import re
from typing import List, Optional

import httpx

from adapters.base import BaseAdapter
from models import RawItem

_DEFAULT_LIMIT = 2
_API_URL = "https://www.brookings.edu/wp-json/wp/v2/article"


def _clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


class BrookingsAdapter(BaseAdapter):

    @property
    def name(self) -> str:
        return "Brookings"

    def __init__(self) -> None:
        self.limit = int(os.environ.get("BROOKINGS_LIMIT", _DEFAULT_LIMIT))

    def fetch(self) -> List[RawItem]:
        params = {
            "per_page": self.limit,
            "orderby": "date",
            "order": "desc",
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(_API_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        items: List[RawItem] = []
        for article in data:
            raw_item = self._to_raw_item(article)
            if raw_item:
                items.append(raw_item)
        return items

    @classmethod
    def _to_raw_item(cls, article: dict) -> Optional[RawItem]:
        wp_id = article.get("id")
        if not wp_id:
            return None

        title_raw = article.get("title", {}).get("rendered", "")
        title = _clean_html(title_raw)
        if not title:
            return None

        yoast = article.get("yoast_head_json") or {}
        abstract = yoast.get("description", "")

        url = article.get("link", "")
        published_at = article.get("date_gmt", "")
        source_type = cls._detect_type(article)
        author = cls._extract_author(article)

        return RawItem(
            id=f"brookings_{wp_id}",
            source_name="Brookings",
            source_type=source_type,
            title=title,
            abstract=abstract,
            url=url,
            published_at=published_at,
            raw_metrics={},
            tags=[],
            author_or_creator=author,
        )

    @staticmethod
    def _detect_type(article: dict) -> str:
        classes = article.get("class_list") or []
        if "article-type-research" in classes:
            return "Paper"
        return "Article"

    @staticmethod
    def _extract_author(article: dict) -> Optional[str]:
        try:
            groups = article["acf"]["helper_people"]["people_groups"]
            names = []
            for group in groups:
                for person in group.get("people", []):
                    if person.get("type") == "manual":
                        name = person.get("write_in", {}).get("name")
                        if name:
                            names.append(name)
            return names[0] if names else None
        except (KeyError, TypeError, IndexError):
            return None
