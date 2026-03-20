"""Y Combinator Blog 适配器 — 通过 RSS feed 获取最新博文。"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import List

import feedparser
import httpx
from email.utils import parsedate_to_datetime

from adapters.base import BaseAdapter
from models import RawItem

_DEFAULT_LIMIT = 2
# YC Blog 发布频率极低（约每月 1-2 篇），不做时间窗口过滤，只按条数截取。
_FEED_URL = "https://www.ycombinator.com/blog/feed"


class YCombinatorAdapter(BaseAdapter):

    @property
    def name(self) -> str:
        return "YC Blog"

    def __init__(self) -> None:
        self.limit = int(os.environ.get("YC_BLOG_LIMIT", _DEFAULT_LIMIT))

    def fetch(self) -> List[RawItem]:
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            resp = client.get(_FEED_URL)
            resp.raise_for_status()
        feed = feedparser.parse(resp.text)

        items: List[RawItem] = []
        for entry in feed.entries:
            published_at = self._parse_date(entry)
            items.append(self._to_raw_item(entry, published_at))
            if len(items) >= self.limit:
                break
        return items

    @staticmethod
    def _parse_date(entry) -> datetime | None:
        parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        if parsed:
            import calendar
            return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
        raw = entry.get("published") or entry.get("updated")
        if not raw:
            return None
        try:
            return parsedate_to_datetime(raw)
        except Exception:
            pass
        try:
            return datetime.fromisoformat(raw)
        except Exception:
            return None

    @staticmethod
    def _make_id(link: str) -> str:
        digest = hashlib.md5(link.encode()).hexdigest()[:12]
        return f"yc_blog_{digest}"

    @staticmethod
    def _to_raw_item(entry, published_at: datetime | None) -> RawItem:
        link = entry.get("link", "")
        summary = entry.get("summary", "")
        tags = [t.get("term", "") for t in entry.get("tags", []) if t.get("term")]

        return RawItem(
            id=YCombinatorAdapter._make_id(link),
            source_name="YC Blog",
            source_type="News",
            title=entry.get("title", ""),
            abstract=summary,
            url=link,
            published_at=published_at.isoformat() if published_at else "",
            raw_metrics={},
            tags=tags,
            author_or_creator=entry.get("author"),
        )
