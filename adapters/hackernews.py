"""HackerNews 适配器 — 通过 Algolia HN Search API 获取热门故事。"""

from __future__ import annotations

import os
import time
from typing import List

import httpx

from adapters.base import BaseAdapter
from models import RawItem

_DEFAULT_HOURS_BACK = 26
_DEFAULT_MIN_POINTS = 50
_DEFAULT_MIN_COMMENTS = 10
_DEFAULT_LIMIT = 6
_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
_HN_ITEM_URL = "https://news.ycombinator.com/item?id="


class HackerNewsAdapter(BaseAdapter):

    @property
    def name(self) -> str:
        return "HackerNews"

    def __init__(self) -> None:
        self.hours_back = int(os.environ.get("HN_HOURS_BACK", _DEFAULT_HOURS_BACK))
        self.min_points = int(os.environ.get("HN_MIN_POINTS", _DEFAULT_MIN_POINTS))
        self.min_comments = int(os.environ.get("HN_MIN_COMMENTS", _DEFAULT_MIN_COMMENTS))
        self.limit = int(os.environ.get("HN_LIMIT", _DEFAULT_LIMIT))

    # ------------------------------------------------------------------

    def fetch(self) -> List[RawItem]:
        since_ts = int(time.time()) - self.hours_back * 3600
        numeric_filters = (
            f"points>{self.min_points},"
            f"num_comments>{self.min_comments},"
            f"created_at_i>{since_ts}"
        )
        params = {
            "tags": "story",
            "numericFilters": numeric_filters,
            "hitsPerPage": self.limit,
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(_SEARCH_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        items: List[RawItem] = []
        for hit in data.get("hits", []):
            items.append(self._to_raw_item(hit))
        return items

    # ------------------------------------------------------------------

    @staticmethod
    def _detect_source_type(title: str) -> str:
        t = title.lower()
        if t.startswith("show hn"):
            return "Tool"
        if t.startswith("ask hn"):
            return "Discussion"
        return "Article"

    @staticmethod
    def _to_raw_item(hit: dict) -> RawItem:
        object_id = hit.get("objectID", "")
        title = hit.get("title") or ""
        story_url = hit.get("url") or ""
        abstract = story_url if story_url else (hit.get("story_text") or "")[:300]
        url = story_url if story_url else f"{_HN_ITEM_URL}{object_id}"

        return RawItem(
            id=f"hn_story_{object_id}",
            source_name="HackerNews",
            source_type=HackerNewsAdapter._detect_source_type(title),
            title=title,
            abstract=abstract,
            url=url,
            published_at=hit.get("created_at", ""),
            raw_metrics={
                "points": hit.get("points", 0),
                "num_comments": hit.get("num_comments", 0),
            },
            tags=hit.get("_tags") or [],
            author_or_creator=hit.get("author"),
        )
