"""Anthropic Blog 适配器 — 通过网页抓取获取最新博文和公告。"""

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

_DEFAULT_LIMIT = 3
_DEFAULT_MAX_AGE_DAYS = 2
_BASE_URL = "https://www.anthropic.com"
_NEWS_URL = "https://www.anthropic.com/news"


def _strip_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", "", text)
    clean = html.unescape(clean).strip()
    return clean[:500]


class AnthropicBlogAdapter(BaseAdapter):

    @property
    def name(self) -> str:
        return "Anthropic Blog"

    def __init__(self) -> None:
        self.limit = int(os.environ.get("ANTHROPIC_BLOG_LIMIT", _DEFAULT_LIMIT))
        self.max_age_days = int(os.environ.get("ANTHROPIC_BLOG_MAX_AGE_DAYS", _DEFAULT_MAX_AGE_DAYS))

    def fetch(self) -> List[RawItem]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        with httpx.Client(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
            resp = client.get(_NEWS_URL)
            resp.raise_for_status()

        # 尝试从 Next.js 嵌入数据中提取
        items = self._try_parse_nextjs(resp.text)
        if items:
            return items

        # 回退到 HTML 解析
        return self._parse_html(resp.text)

    def _try_parse_nextjs(self, page_html: str) -> List[RawItem]:
        """从 Next.js __NEXT_DATA__ 或 self.__next_f.push() 中提取文章。"""
        items: List[RawItem] = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.max_age_days)

        # 方式 1: __NEXT_DATA__
        json_match = re.search(
            r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            page_html,
            re.DOTALL,
        )
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                posts = self._find_posts(data)
                return self._build_items(posts, cutoff)
            except (json.JSONDecodeError, KeyError):
                pass

        # 方式 2: 从 self.__next_f.push() 数据中提取文章对象
        # 匹配包含 "publishedOn" 的 JSON 对象片段
        post_pattern = re.compile(
            r'\{[^{}]*?"title"\s*:\s*"([^"]+)"[^{}]*?"slug"\s*:\s*\{[^{}]*?"current"\s*:\s*"([^"]+)"[^{}]*?\}[^{}]*?"publishedOn"\s*:\s*"([^"]+)"[^{}]*?\}',
        )
        for title, slug, published_on in post_pattern.findall(page_html):
            if len(items) >= self.limit:
                break
            published_at = self._parse_date(published_on)
            if published_at and published_at < cutoff:
                continue
            url = f"{_BASE_URL}/news/{slug}"
            items.append(RawItem(
                id=self._make_id(url),
                source_name="Anthropic Blog",
                source_type="Article",
                title=title,
                abstract="",
                url=url,
                published_at=published_at.isoformat() if published_at else "",
                raw_metrics={},
                tags=[],
                author_or_creator=None,
            ))

        # 方式 3: 更宽泛地匹配 — 从序列化数据中提取
        if not items:
            # 匹配 "title":"xxx" 和 "slug":{"current":"xxx"} 模式
            title_slug_pairs = re.findall(
                r'"title":"((?:[^"\\]|\\.)+)".*?"slug":\{"current":"((?:[^"\\]|\\.)+)"\}',
                page_html,
            )
            for title, slug in title_slug_pairs:
                if len(items) >= self.limit:
                    break
                url = f"{_BASE_URL}/news/{slug}"
                items.append(RawItem(
                    id=self._make_id(url),
                    source_name="Anthropic Blog",
                    source_type="Article",
                    title=title.encode().decode("unicode_escape", errors="replace"),
                    abstract="",
                    url=url,
                    published_at=datetime.now(timezone.utc).date().isoformat(),
                    raw_metrics={},
                    tags=[],
                    author_or_creator=None,
                ))

        return items

    def _find_posts(self, data, depth: int = 0) -> list[dict]:
        """递归搜索 JSON 中的 posts 列表。"""
        if depth > 5:
            return []
        if isinstance(data, list):
            if data and isinstance(data[0], dict) and "title" in data[0] and "slug" in data[0]:
                return data
            results = []
            for item in data:
                results.extend(self._find_posts(item, depth + 1))
            return results
        if isinstance(data, dict):
            for key in ("posts", "items", "articles", "data", "props", "pageProps"):
                if key in data:
                    result = self._find_posts(data[key], depth + 1)
                    if result:
                        return result
        return []

    def _build_items(self, posts: list[dict], cutoff: datetime) -> List[RawItem]:
        items: List[RawItem] = []
        for post in posts:
            if len(items) >= self.limit:
                break
            title = post.get("title", "")
            if not title:
                continue
            slug = post.get("slug", {})
            if isinstance(slug, dict):
                slug = slug.get("current", "")
            url = f"{_BASE_URL}/news/{slug}" if slug else ""
            published = post.get("publishedOn", "") or post.get("published_at", "")
            published_at = self._parse_date(published)
            if published_at and published_at < cutoff:
                continue
            summary = post.get("summary", "") or post.get("description", "") or ""

            items.append(RawItem(
                id=self._make_id(url or title),
                source_name="Anthropic Blog",
                source_type="Article",
                title=title,
                abstract=_strip_html(summary),
                url=url,
                published_at=published_at.isoformat() if published_at else "",
                raw_metrics={},
                tags=[s.get("label", "") for s in post.get("subjects", []) if isinstance(s, dict)] if isinstance(post.get("subjects"), list) else [],
                author_or_creator=None,
            ))
        return items

    def _parse_html(self, page_html: str) -> List[RawItem]:
        """回退：从 HTML 链接中提取文章。"""
        items: List[RawItem] = []
        seen_urls: set[str] = set()

        # Anthropic news 页面的文章链接格式: /news/slug-name
        pattern = re.compile(r'href="(/news/[a-z0-9][a-z0-9\-]+)"')
        for path in pattern.findall(page_html):
            if path == "/news":
                continue
            if len(items) >= self.limit:
                break
            url = f"{_BASE_URL}{path}"
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # 尝试从 URL slug 生成标题
            slug = path.split("/")[-1]
            title = slug.replace("-", " ").title()

            items.append(RawItem(
                id=self._make_id(url),
                source_name="Anthropic Blog",
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
            return datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            return None

    @staticmethod
    def _make_id(link: str) -> str:
        digest = hashlib.md5(link.encode()).hexdigest()[:12]
        return f"anthropic_blog_{digest}"
