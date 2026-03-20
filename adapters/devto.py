"""Dev.to 适配器 — 获取过去 N 天最热门的技术文章。"""

from __future__ import annotations

import os
from typing import List

import httpx

from adapters.base import BaseAdapter
from models import RawItem

_DEFAULT_TOP_DAYS = 1
_DEFAULT_LIMIT = 5
_API_URL = "https://dev.to/api/articles"


class DevToAdapter(BaseAdapter):

    @property
    def name(self) -> str:
        return "Dev.to"

    def __init__(self) -> None:
        self.top_days = int(os.environ.get("DEVTO_TOP_DAYS", _DEFAULT_TOP_DAYS))
        self.limit = int(os.environ.get("DEVTO_LIMIT", _DEFAULT_LIMIT))

    def fetch(self) -> List[RawItem]:
        params = {
            "top": self.top_days,
            "per_page": self.limit,
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(_API_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        items: List[RawItem] = []
        for article in data:
            items.append(self._to_raw_item(article))
        return items

    @staticmethod
    def _to_raw_item(article: dict) -> RawItem:
        article_id = article.get("id", "")
        path = article.get("path", "")
        url = f"https://dev.to{path}" if path else article.get("canonical_url", "")
        tag_list = article.get("tag_list", [])
        if isinstance(tag_list, str):
            tag_list = [t.strip() for t in tag_list.split(",") if t.strip()]

        user = article.get("user") or {}

        return RawItem(
            id=f"devto_article_{article_id}",
            source_name="Dev.to",
            source_type="Article",
            title=article.get("title", ""),
            abstract=article.get("description", ""),
            url=url,
            published_at=article.get("published_at", ""),
            raw_metrics={
                "public_reactions_count": article.get("public_reactions_count", 0),
                "comments_count": article.get("comments_count", 0),
                "reading_time_minutes": article.get("reading_time_minutes", 0),
            },
            tags=tag_list,
            author_or_creator=user.get("name"),
        )
