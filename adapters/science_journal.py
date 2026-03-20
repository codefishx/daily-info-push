"""Science (AAAS) 适配器 — 通过 RSS feed 获取最新科学新闻与论文。"""

from __future__ import annotations

import hashlib
import html
import os
import re
from datetime import datetime, timezone, timedelta
from typing import List

import feedparser
import httpx

from adapters.base import BaseAdapter
from models import RawItem

_DEFAULT_LIMIT = 3
_DEFAULT_MAX_AGE_DAYS = 5
_DEFAULT_FEEDS = [
    "https://www.science.org/rss/news_current.xml",
    "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=science",
]


def _strip_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", "", text)
    clean = html.unescape(clean).strip()
    return clean[:500]


class ScienceJournalAdapter(BaseAdapter):

    @property
    def name(self) -> str:
        return "Science"

    def __init__(self) -> None:
        self.limit = int(os.environ.get("SCIENCE_LIMIT", _DEFAULT_LIMIT))
        self.max_age_days = int(os.environ.get("SCIENCE_MAX_AGE_DAYS", _DEFAULT_MAX_AGE_DAYS))

    def fetch(self) -> List[RawItem]:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; daily-info-push/1.0)"}
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.max_age_days)
        items: List[RawItem] = []
        seen_urls: set[str] = set()

        with httpx.Client(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
            for feed_url in _DEFAULT_FEEDS:
                try:
                    resp = client.get(feed_url)
                    resp.raise_for_status()
                    feed = feedparser.parse(resp.text)
                except Exception:
                    continue
                # 判断 feed 类型：news feed 为 Article，TOC feed 为 Paper
                is_news = "news" in feed_url
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
                    items.append(self._to_raw_item(entry, published_at, is_news))
                if len(items) >= self.limit:
                    break
        return items[:self.limit]

    @staticmethod
    def _parse_date(entry) -> datetime | None:
        import calendar
        parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        if parsed:
            return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
        raw = entry.get("published") or entry.get("updated") or entry.get("dc_date", "")
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return None

    @staticmethod
    def _make_id(link: str) -> str:
        digest = hashlib.md5(link.encode()).hexdigest()[:12]
        return f"science_{digest}"

    @staticmethod
    def _to_raw_item(entry, published_at: datetime | None, is_news: bool) -> RawItem:
        link = entry.get("link", "")
        summary = _strip_html(entry.get("summary", "") or entry.get("description", ""))
        tags = [t.get("term", "") for t in entry.get("tags", []) if t.get("term")]
        author = entry.get("author") or entry.get("dc_creator")

        return RawItem(
            id=ScienceJournalAdapter._make_id(link),
            source_name="Science",
            source_type="Article" if is_news else "Paper",
            title=entry.get("title", ""),
            abstract=summary,
            url=link,
            published_at=published_at.isoformat() if published_at else "",
            raw_metrics={},
            tags=tags,
            author_or_creator=author,
        )
