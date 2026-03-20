"""Financial Times 适配器 — 通过 RSS feed 获取多板块金融新闻标题与摘要。"""

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

_DEFAULT_LIMIT = 3
_DEFAULT_MAX_AGE_DAYS = 2
_DEFAULT_FEEDS = [
    "https://www.ft.com/rss/home",
    "https://www.ft.com/technology?format=rss",
    "https://www.ft.com/global-economy?format=rss",
]


def _strip_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", "", text)
    clean = html.unescape(clean).strip()
    return clean[:500]


class FTAdapter(BaseAdapter):

    @property
    def name(self) -> str:
        return "Financial Times"

    def __init__(self) -> None:
        self.limit = int(os.environ.get("FT_LIMIT", _DEFAULT_LIMIT))
        self.max_age_days = int(os.environ.get("FT_MAX_AGE_DAYS", _DEFAULT_MAX_AGE_DAYS))
        feeds_env = os.environ.get("FT_FEEDS", "")
        self.feeds = [u.strip() for u in feeds_env.split(",") if u.strip()] if feeds_env else _DEFAULT_FEEDS

    def fetch(self) -> List[RawItem]:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; daily-info-push/1.0)"}
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.max_age_days)
        items: List[RawItem] = []
        seen_urls: set[str] = set()

        with httpx.Client(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
            for feed_url in self.feeds:
                try:
                    resp = client.get(feed_url)
                    resp.raise_for_status()
                    feed = feedparser.parse(resp.text)
                except Exception:
                    continue
                for entry in feed.entries:
                    if len(items) >= self.limit:
                        break
                    link = entry.get("link", "")
                    if link in seen_urls:
                        continue
                    seen_urls.add(link)
                    published_at = self._parse_date(entry)
                    if published_at and published_at < cutoff:
                        continue
                    items.append(self._to_raw_item(entry, published_at))
                if len(items) >= self.limit:
                    break
        return items[:self.limit]

    @staticmethod
    def _parse_date(entry) -> datetime | None:
        raw = entry.get("published") or entry.get("updated")
        if not raw:
            return None
        try:
            return parsedate_to_datetime(raw)
        except Exception:
            return None

    @staticmethod
    def _make_id(link: str) -> str:
        digest = hashlib.md5(link.encode()).hexdigest()[:12]
        return f"ft_{digest}"

    @staticmethod
    def _to_raw_item(entry, published_at: datetime | None) -> RawItem:
        link = entry.get("link", "")
        summary = _strip_html(entry.get("summary", "") or entry.get("description", ""))
        tags = [t.get("term", "") for t in entry.get("tags", []) if t.get("term")]

        return RawItem(
            id=FTAdapter._make_id(link),
            source_name="Financial Times",
            source_type="News",
            title=entry.get("title", ""),
            abstract=summary,
            url=link,
            published_at=published_at.isoformat() if published_at else "",
            raw_metrics={},
            tags=tags,
            author_or_creator=entry.get("author"),
        )
