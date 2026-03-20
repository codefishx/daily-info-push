"""Nature 期刊适配器 — 通过官方 RSS feed 获取最新论文摘要。"""

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
    "https://www.nature.com/nature.rss",
]


def _strip_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", "", text)
    clean = html.unescape(clean).strip()
    return clean[:500]


class NatureAdapter(BaseAdapter):

    @property
    def name(self) -> str:
        return "Nature"

    def __init__(self) -> None:
        self.limit = int(os.environ.get("NATURE_LIMIT", _DEFAULT_LIMIT))
        self.max_age_days = int(os.environ.get("NATURE_MAX_AGE_DAYS", _DEFAULT_MAX_AGE_DAYS))
        feeds_env = os.environ.get("NATURE_FEEDS", "")
        self.feeds = [u.strip() for u in feeds_env.split(",") if u.strip()] if feeds_env else _DEFAULT_FEEDS

    def fetch(self) -> List[RawItem]:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; daily-info-push/1.0)"}
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.max_age_days)
        items: List[RawItem] = []

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
                    published_at = self._parse_date(entry)
                    if published_at and published_at < cutoff:
                        continue
                    items.append(self._to_raw_item(entry, published_at))
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
        return f"nature_{digest}"

    @staticmethod
    def _to_raw_item(entry, published_at: datetime | None) -> RawItem:
        link = entry.get("link", "")
        summary = _strip_html(entry.get("summary", "") or entry.get("description", ""))
        tags = [t.get("term", "") for t in entry.get("tags", []) if t.get("term")]
        # Nature RSS 的作者信息可能在 dc:creator
        author = entry.get("author") or entry.get("dc_creator")

        return RawItem(
            id=NatureAdapter._make_id(link),
            source_name="Nature",
            source_type="Paper",
            title=entry.get("title", ""),
            abstract=summary,
            url=link,
            published_at=published_at.isoformat() if published_at else "",
            raw_metrics={},
            tags=tags,
            author_or_creator=author,
        )
