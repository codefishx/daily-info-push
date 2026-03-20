"""NBER Working Papers 适配器 — 通过 RSS feed 获取最新工作论文。

使用 feedparser 解析 RSS，以容忍 NBER feed 中偶尔出现的
未转义 XML 特殊字符（如 description 里的 '<', '>'）。
"""

from __future__ import annotations

import os
import re
from typing import List

import feedparser
import httpx

from adapters.base import BaseAdapter
from models import RawItem

_DEFAULT_LIMIT = 3
_RSS_URL = "https://back.nber.org/rss/new.xml"


class NBERAdapter(BaseAdapter):

    @property
    def name(self) -> str:
        return "NBER Working Papers"

    def __init__(self) -> None:
        self.limit = int(os.environ.get("NBER_LIMIT", _DEFAULT_LIMIT))

    def fetch(self) -> List[RawItem]:
        headers = {"User-Agent": "daily-info-push/1.0 (NBER-Adapter)"}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(_RSS_URL, headers=headers)
            resp.raise_for_status()

        feed = feedparser.parse(resp.text)
        if feed.bozo and not feed.entries:
            raise ValueError(f"RSS 解析失败: {feed.bozo_exception}")

        items: List[RawItem] = []
        for entry in feed.entries:
            if len(items) >= self.limit:
                break
            raw_item = self._parse_entry(entry)
            if raw_item:
                items.append(raw_item)
        return items

    @classmethod
    def _parse_entry(cls, entry: feedparser.FeedParserDict) -> RawItem | None:
        raw_title = (entry.get("title") or "").strip()
        if not raw_title:
            return None

        title, author = cls._split_title_author(raw_title)
        description = (entry.get("summary") or "").strip()
        link = (entry.get("link") or "").strip()

        link = link.split("#")[0]
        paper_num = cls._extract_paper_number(link)

        return RawItem(
            id=f"nber_wp_{paper_num}" if paper_num else f"nber_{title[:40]}",
            source_name="NBER Working Papers",
            source_type="Paper",
            title=title,
            abstract=description[:500],
            url=link,
            published_at="",
            raw_metrics={"paper_number": int(paper_num)} if paper_num else {},
            tags=[],
            author_or_creator=author or None,
        )

    @staticmethod
    def _split_title_author(raw_title: str) -> tuple[str, str]:
        """Split NBER's 'Title -- by Author1, Author2' format."""
        if " -- by " in raw_title:
            title, author = raw_title.split(" -- by ", 1)
            return title.strip(), author.strip()
        return raw_title, ""

    @staticmethod
    def _extract_paper_number(url: str) -> str:
        m = re.search(r"/papers/w(\d+)", url)
        return m.group(1) if m else ""
