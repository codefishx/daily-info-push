"""Lobste.rs 适配器 — 获取热门技术故事。"""

from __future__ import annotations

import os
from typing import List

import httpx

from adapters.base import BaseAdapter
from models import RawItem

_DEFAULT_LIMIT = 5
_DEFAULT_MIN_SCORE = 5
_HOTTEST_URL = "https://lobste.rs/hottest.json"


class LobstersAdapter(BaseAdapter):

    @property
    def name(self) -> str:
        return "Lobste.rs"

    def __init__(self) -> None:
        self.limit = int(os.environ.get("LOBSTERS_LIMIT", _DEFAULT_LIMIT))
        self.min_score = int(os.environ.get("LOBSTERS_MIN_SCORE", _DEFAULT_MIN_SCORE))

    def fetch(self) -> List[RawItem]:
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(_HOTTEST_URL)
            resp.raise_for_status()
            data = resp.json()

        items: List[RawItem] = []
        for story in data:
            if story.get("score", 0) < self.min_score:
                continue
            items.append(self._to_raw_item(story))
            if len(items) >= self.limit:
                break
        return items

    @staticmethod
    def _to_raw_item(story: dict) -> RawItem:
        short_id = story.get("short_id", "")
        url = story.get("url") or story.get("short_id_url", "")
        abstract = story.get("description_plain") or url

        return RawItem(
            id=f"lobsters_story_{short_id}",
            source_name="Lobste.rs",
            source_type="Article",
            title=story.get("title", ""),
            abstract=abstract,
            url=url,
            published_at=story.get("created_at", ""),
            raw_metrics={
                "score": story.get("score", 0),
                "comment_count": story.get("comment_count", 0),
            },
            tags=story.get("tags") or [],
            author_or_creator=story.get("submitter_user"),
        )
