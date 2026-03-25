"""InfoQ 中文适配器 — 通过 RSS feed 获取最新技术文章。"""

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

_DEFAULT_LIMIT = 5
_DEFAULT_MAX_AGE_DAYS = 2
_FEED_URL = "https://www.infoq.cn/feed"


def _strip_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", "", text)
    clean = html.unescape(clean).strip()
    return clean[:500]


class InfoQCNAdapter(BaseAdapter):

    @property
    def name(self) -> str:
        return "InfoQ CN"

    def __init__(self) -> None:
        self.limit = int(os.environ.get("INFOQ_CN_LIMIT", _DEFAULT_LIMIT))
        self.max_age_days = int(os.environ.get("INFOQ_CN_MAX_AGE_DAYS", _DEFAULT_MAX_AGE_DAYS))

    def fetch(self) -> List[RawItem]:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; daily-info-push/1.0)"}
        with httpx.Client(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
            resp = client.get(_FEED_URL)
            resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.max_age_days)

        items: List[RawItem] = []
        for entry in feed.entries:
            if len(items) >= self.limit:
                break
            published_at = self._parse_date(entry)
            if published_at and published_at < cutoff:
                continue
            items.append(self._to_raw_item(entry, published_at))
        return items

    @staticmethod
    def _parse_date(entry) -> datetime | None:
        import calendar
        parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        if parsed:
            return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
        raw = entry.get("published") or entry.get("updated")
        if not raw:
            return None
        try:
            return parsedate_to_datetime(raw)
        except Exception:
            try:
                return datetime.fromisoformat(raw)
            except Exception:
                return None

    @staticmethod
    def _make_id(link: str) -> str:
        digest = hashlib.md5(link.encode()).hexdigest()[:12]
        return f"infoq_cn_{digest}"

    @staticmethod
    def _to_raw_item(entry, published_at: datetime | None) -> RawItem:
        link = entry.get("link", "")
        summary = _strip_html(entry.get("summary", "") or entry.get("description", ""))
        tags = [t.get("term", "") for t in entry.get("tags", []) if t.get("term")]

        return RawItem(
            id=InfoQCNAdapter._make_id(link),
            source_name="InfoQ CN",
            source_type="Article",
            title=entry.get("title", ""),
            abstract=summary,
            url=link,
            published_at=published_at.isoformat() if published_at else "",
            raw_metrics={},
            tags=tags,
            author_or_creator=entry.get("author"),
        )
