"""极客公园适配器 — 通过网页抓取获取最新科技产品资讯。"""

from __future__ import annotations

import hashlib
import html
import os
import re
from datetime import datetime, timezone, timedelta
from typing import List

import httpx

from adapters.base import BaseAdapter
from models import RawItem

_DEFAULT_LIMIT = 5
_DEFAULT_MAX_AGE_DAYS = 3
_BASE_URL = "https://www.geekpark.net"
_LIST_URL = "https://www.geekpark.net/"


def _strip_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", "", text)
    clean = html.unescape(clean).strip()
    return clean[:500]


class GeekParkAdapter(BaseAdapter):

    @property
    def name(self) -> str:
        return "极客公园"

    def __init__(self) -> None:
        self.limit = int(os.environ.get("GEEKPARK_LIMIT", _DEFAULT_LIMIT))
        self.max_age_days = int(os.environ.get("GEEKPARK_MAX_AGE_DAYS", _DEFAULT_MAX_AGE_DAYS))

    def fetch(self) -> List[RawItem]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        with httpx.Client(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
            resp = client.get(_LIST_URL)
            resp.raise_for_status()

        return self._parse_articles(resp.text)

    def _parse_articles(self, page_html: str) -> List[RawItem]:
        """从首页 HTML 中提取文章列表。"""
        items: List[RawItem] = []

        # 尝试匹配文章链接和标题 — 极客公园文章 URL 格式: /news/XXXXX
        article_pattern = re.compile(
            r'<a[^>]+href="(/news/\d+)"[^>]*>.*?'
            r'<[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</[^>]+>',
            re.DOTALL,
        )
        # 备用：更宽泛的匹配
        fallback_pattern = re.compile(
            r'href="(/news/\d+)"[^>]*>([^<]+)</a>',
        )

        seen_urls: set[str] = set()
        matches = article_pattern.findall(page_html) or fallback_pattern.findall(page_html)

        for path, raw_title in matches:
            if len(items) >= self.limit:
                break
            url = f"{_BASE_URL}{path}"
            if url in seen_urls:
                continue
            seen_urls.add(url)

            title = _strip_html(raw_title).strip()
            if not title:
                continue

            items.append(RawItem(
                id=self._make_id(url),
                source_name="极客公园",
                source_type="Article",
                title=title,
                abstract="",
                url=url,
                published_at=datetime.now(timezone.utc).date().isoformat(),
                raw_metrics={},
                tags=[],
                author_or_creator=None,
            ))
        return items

    @staticmethod
    def _make_id(link: str) -> str:
        digest = hashlib.md5(link.encode()).hexdigest()[:12]
        return f"geekpark_{digest}"
