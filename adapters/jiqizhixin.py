"""机器之心适配器 — 通过网页抓取获取最新 AI 技术文章。"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
from datetime import datetime, timezone, timedelta
from typing import List

import httpx

from adapters.base import BaseAdapter
from models import RawItem

_DEFAULT_LIMIT = 5
_DEFAULT_MAX_AGE_DAYS = 2
_BASE_URL = "https://www.jiqizhixin.com"
_LIST_URL = "https://www.jiqizhixin.com/"


def _strip_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", "", text)
    clean = html.unescape(clean).strip()
    return clean[:500]


class JiqizhixinAdapter(BaseAdapter):

    @property
    def name(self) -> str:
        return "机器之心"

    def __init__(self) -> None:
        self.limit = int(os.environ.get("JIQIZHIXIN_LIMIT", _DEFAULT_LIMIT))
        self.max_age_days = int(os.environ.get("JIQIZHIXIN_MAX_AGE_DAYS", _DEFAULT_MAX_AGE_DAYS))

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

        # 尝试从页面中提取 JSON 数据（Next.js / Nuxt.js 嵌入的数据）
        items = self._try_parse_json_data(resp.text)
        if items:
            return items

        # 回退到 HTML 解析
        return self._parse_html(resp.text)

    def _try_parse_json_data(self, page_html: str) -> List[RawItem]:
        """尝试从嵌入的 JSON 数据中提取文章。"""
        items: List[RawItem] = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.max_age_days)

        # 匹配 __NEXT_DATA__ 或类似的嵌入 JSON
        json_match = re.search(
            r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            page_html,
            re.DOTALL,
        )
        if not json_match:
            return []

        try:
            data = json.loads(json_match.group(1))
        except (json.JSONDecodeError, IndexError):
            return []

        # 递归搜索文章数据
        articles = self._find_articles(data)
        for article in articles:
            if len(items) >= self.limit:
                break

            title = article.get("title", "")
            if not title:
                continue

            slug = article.get("slug", "") or article.get("id", "")
            url = article.get("url", "")
            if not url and slug:
                url = f"{_BASE_URL}/articles/{slug}"

            published = article.get("published_at", "") or article.get("created_at", "")
            published_at = self._parse_date(published)
            if published_at and published_at < cutoff:
                continue

            summary = article.get("summary", "") or article.get("description", "") or ""

            items.append(RawItem(
                id=self._make_id(url or title),
                source_name="机器之心",
                source_type="Article",
                title=title,
                abstract=_strip_html(summary),
                url=url,
                published_at=published_at.isoformat() if published_at else "",
                raw_metrics={},
                tags=article.get("tags", []) if isinstance(article.get("tags"), list) else [],
                author_or_creator=article.get("author"),
            ))

        return items

    def _find_articles(self, data, depth: int = 0) -> list[dict]:
        """递归搜索 JSON 中的文章列表。"""
        if depth > 5:
            return []
        if isinstance(data, list):
            # 检查是否为文章列表
            if data and isinstance(data[0], dict) and "title" in data[0]:
                return data
            results = []
            for item in data:
                results.extend(self._find_articles(item, depth + 1))
            return results
        if isinstance(data, dict):
            # 检查是否包含 articles 键
            for key in ("articles", "posts", "items", "data", "list", "props", "pageProps"):
                if key in data:
                    result = self._find_articles(data[key], depth + 1)
                    if result:
                        return result
        return []

    def _parse_html(self, page_html: str) -> List[RawItem]:
        """从 HTML 中提取文章。"""
        items: List[RawItem] = []
        seen_urls: set[str] = set()

        # 匹配文章链接 — 机器之心文章 URL 格式: /articles/XXXXX 或 /dailies/XXXXX
        pattern = re.compile(
            r'href="(/(?:articles|dailies)/[^"]+)"[^>]*>([^<]*)</a>',
        )

        for path, raw_title in pattern.findall(page_html):
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
                source_name="机器之心",
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
    def _parse_date(raw: str) -> datetime | None:
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            pass
        try:
            return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except Exception:
            return None

    @staticmethod
    def _make_id(link: str) -> str:
        digest = hashlib.md5(link.encode()).hexdigest()[:12]
        return f"jiqizhixin_{digest}"
