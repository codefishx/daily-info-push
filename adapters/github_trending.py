"""GitHub Trending 适配器 — 通过 GitHub Search API 获取近期高星仓库。"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import List

import httpx

from adapters.base import BaseAdapter
from models import RawItem

_DEFAULT_DAYS_BACK = 30
_DEFAULT_MIN_STARS = 1000
_DEFAULT_LIMIT = 5
_SEARCH_URL = "https://api.github.com/search/repositories"


class GitHubTrendingAdapter(BaseAdapter):

    @property
    def name(self) -> str:
        return "GitHub Trending"

    def __init__(self) -> None:
        self.days_back = int(os.environ.get("GITHUB_DAYS_BACK", _DEFAULT_DAYS_BACK))
        self.min_stars = int(os.environ.get("GITHUB_MIN_STARS", _DEFAULT_MIN_STARS))
        self.limit = int(os.environ.get("GITHUB_LIMIT", _DEFAULT_LIMIT))
        self.token = os.environ.get("GITHUB_TOKEN", "")

    # ------------------------------------------------------------------

    def fetch(self) -> List[RawItem]:
        since = (datetime.now(timezone.utc) - timedelta(days=self.days_back)).strftime("%Y-%m-%d")
        q = f"created:>{since} stars:>{self.min_stars} archived:false fork:false"
        params = {
            "q": q,
            "sort": "stars",
            "order": "desc",
            "per_page": self.limit,
        }
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(_SEARCH_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        items: List[RawItem] = []
        for repo in data.get("items", []):
            items.append(self._to_raw_item(repo))
        return items

    # ------------------------------------------------------------------

    @staticmethod
    def _make_id(html_url: str) -> str:
        digest = hashlib.md5(html_url.encode()).hexdigest()[:12]
        return f"github_repo_{digest}"

    @staticmethod
    def _to_raw_item(repo: dict) -> RawItem:
        return RawItem(
            id=GitHubTrendingAdapter._make_id(repo["html_url"]),
            source_name="GitHub Trending",
            source_type="Repository",
            title=repo.get("full_name", ""),
            abstract=repo.get("description") or "",
            url=repo["html_url"],
            published_at=repo.get("created_at", ""),
            raw_metrics={
                "stars": repo.get("stargazers_count", 0),
                "forks": repo.get("forks_count", 0),
                "open_issues": repo.get("open_issues_count", 0),
            },
            tags=repo.get("topics") or [],
            author_or_creator=repo.get("owner", {}).get("login"),
        )
