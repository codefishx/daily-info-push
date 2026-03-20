"""NewsAPI 适配器 — 通过 NewsAPI 获取多分类热门新闻。"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Dict, List

import httpx

from adapters.base import BaseAdapter
from models import RawItem

_CATEGORIES = ["business", "technology", "general", "science", "health"]
_DEFAULT_PER_CATEGORY_LIMIT = 3
_DEFAULT_TOTAL_LIMIT = 10  # 0 表示不限制
_DEFAULT_COUNTRY = "us"
_API_URL = "https://newsapi.org/v2/top-headlines"

logger = logging.getLogger(__name__)


class NewsAPIAdapter(BaseAdapter):

    @property
    def name(self) -> str:
        return "NewsAPI"

    def __init__(self) -> None:
        self.api_key = os.environ.get("NEWSAPI_KEY", "")
        self.country = os.environ.get("NEWSAPI_COUNTRY", _DEFAULT_COUNTRY)
        self.per_category_limit = int(
            os.environ.get("NEWSAPI_PER_CATEGORY_LIMIT", _DEFAULT_PER_CATEGORY_LIMIT)
        )
        self.total_limit = int(
            os.environ.get("NEWSAPI_TOTAL_LIMIT", _DEFAULT_TOTAL_LIMIT)
        )
        # 单独的 category limit，JSON 格式，例如: {"technology": 5, "science": 2}
        # 填写了则覆盖该分类的 per_category_limit
        self.category_limits: Dict[str, int] = json.loads(
            os.environ.get("NEWSAPI_CATEGORY_LIMITS", "{}")
        )

    def fetch(self) -> List[RawItem]:
        if not self.api_key:
            raise RuntimeError("NEWSAPI_KEY environment variable is required")

        headers = {"X-Api-Key": self.api_key}
        items: List[RawItem] = []
        seen_urls: set[str] = set()

        with httpx.Client(timeout=self.timeout) as client:
            for category in _CATEGORIES:
                limit = self.category_limits.get(category, self.per_category_limit)
                params = {
                    "category": category,
                    "pageSize": limit,
                    "country": self.country,
                }
                try:
                    resp = client.get(_API_URL, params=params, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception:
                    logger.warning("NewsAPI fetch failed for category=%s", category, exc_info=True)
                    continue

                if data.get("status") != "ok":
                    logger.warning("NewsAPI error for category=%s: %s", category, data.get("message", "unknown"))
                    continue

                for article in data.get("articles", []):
                    url = article.get("url", "")
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    items.append(self._to_raw_item(article, category))

        if self.total_limit > 0:
            items = items[:self.total_limit]

        return items

    @staticmethod
    def _make_id(url: str) -> str:
        digest = hashlib.md5(url.encode()).hexdigest()[:12]
        return f"newsapi_{digest}"

    @staticmethod
    def _to_raw_item(article: dict, category: str) -> RawItem:
        url = article.get("url", "")
        source = article.get("source") or {}
        source_name_val = source.get("name", "")

        tags = [category]
        if source_name_val:
            tags.append(source_name_val)

        return RawItem(
            id=NewsAPIAdapter._make_id(url),
            source_name="NewsAPI",
            source_type="News",
            title=article.get("title", ""),
            abstract=article.get("description") or "",
            url=url,
            published_at=article.get("publishedAt", ""),
            raw_metrics={"source": source_name_val, "category": category},
            tags=tags,
            author_or_creator=article.get("author"),
        )
