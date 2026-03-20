"""Substack 适配器 — 从多个高质量 Substack 专栏的 RSS/Atom feed 获取最新文章。

使用 httpx 下载 feed 内容（带超时），feedparser 仅负责解析，避免 urllib 连接不稳定。
"""

from __future__ import annotations

import hashlib
import html
import os
import re
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import List

import feedparser
import httpx

from adapters.base import BaseAdapter
from models import RawItem

_DEFAULT_MAX_AGE_DAYS = 3
_DEFAULT_LIMIT_PER_FEED = 2
_DEFAULT_FEEDS = [
    "https://simonwillison.net/atom/everything/",
    "https://www.astralcodexten.com/feed",
    "https://www.oneusefulthing.org/feed",
    "https://semianalysis.com/feed",
    "https://thealgorithmicbridge.substack.com/feed",
]


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode entities, truncate to 500 chars."""
    clean = re.sub(r"<[^>]+>", "", text)
    clean = html.unescape(clean).strip()
    return clean[:500]


class SubstackAdapter(BaseAdapter):

    @property
    def name(self) -> str:
        return "Substack"

    def __init__(self) -> None:
        self.max_age_days = int(os.environ.get("SUBSTACK_MAX_AGE_DAYS", _DEFAULT_MAX_AGE_DAYS))
        self.limit_per_feed = int(os.environ.get("SUBSTACK_LIMIT_PER_FEED", _DEFAULT_LIMIT_PER_FEED))
        feeds_env = os.environ.get("SUBSTACK_FEEDS", "")
        self.feeds = [u.strip() for u in feeds_env.split(",") if u.strip()] if feeds_env else _DEFAULT_FEEDS

    def fetch(self) -> List[RawItem]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.max_age_days)
        items: List[RawItem] = []

        headers = {"User-Agent": "Mozilla/5.0 (compatible; daily-info-push/1.0; +https://github.com)"}
        with httpx.Client(timeout=self.timeout, headers=headers, follow_redirects=True) as client:
            for feed_url in self.feeds:
                try:
                    resp = client.get(feed_url)
                    resp.raise_for_status()
                    feed = feedparser.parse(resp.text)
                except Exception:
                    continue
                count = 0
                for entry in feed.entries:
                    if count >= self.limit_per_feed:
                        break
                    published_at = self._parse_date(entry)
                    if published_at and published_at < cutoff:
                        continue
                    items.append(self._to_raw_item(entry, published_at))
                    count += 1
        return items

    @staticmethod
    def _parse_date(entry) -> datetime | None:
        # 优先使用 feedparser 已解析好的 time.struct_time（兼容 RSS 和 Atom）
        parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        if parsed:
            import calendar
            return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
        # 兜底：尝试 RFC 2822 字符串
        raw = entry.get("published") or entry.get("updated")
        if not raw:
            return None
        try:
            return parsedate_to_datetime(raw)
        except Exception:
            pass
        # 再兜底：ISO 8601 字符串
        try:
            return datetime.fromisoformat(raw)
        except Exception:
            return None

    @staticmethod
    def _make_id(link: str) -> str:
        digest = hashlib.md5(link.encode()).hexdigest()[:12]
        return f"substack_{digest}"

    @staticmethod
    def _to_raw_item(entry, published_at: datetime | None) -> RawItem:
        link = entry.get("link", "")
        summary = _strip_html(entry.get("summary", ""))
        tags = [t.get("term", "") for t in entry.get("tags", []) if t.get("term")]

        return RawItem(
            id=SubstackAdapter._make_id(link),
            source_name="Substack",
            source_type="Article",
            title=entry.get("title", ""),
            abstract=summary,
            url=link,
            published_at=published_at.isoformat() if published_at else "",
            raw_metrics={},
            tags=tags,
            author_or_creator=entry.get("author"),
        )
