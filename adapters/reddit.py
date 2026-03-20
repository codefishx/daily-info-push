"""Reddit 适配器 — 通过 PRAW (OAuth2) 获取指定 subreddit 的每日热门帖子。

认证方式：Reddit Script App（个人免费用途）。
需要的环境变量：
    REDDIT_CLIENT_ID      — App 的 client_id
    REDDIT_CLIENT_SECRET  — App 的 client_secret
    REDDIT_USERNAME       — Reddit 账号用户名
    REDDIT_PASSWORD       — Reddit 账号密码

在 https://www.reddit.com/prefs/apps 创建 "script" 类型的应用即可获取前两项。
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import List

import praw

from adapters.base import BaseAdapter
from models import RawItem

_DEFAULT_SUBREDDITS = "MachineLearning,LocalLLaMA,hardware,dataengineering"
_DEFAULT_LIMIT_PER_SUB = 10
_DEFAULT_TIME_FILTER = "day"
_USER_AGENT = "python:daily-info-push:v1.0 (by /u/{username})"


class RedditAdapter(BaseAdapter):

    @property
    def name(self) -> str:
        return "Reddit"

    def __init__(self) -> None:
        subs = os.environ.get("REDDIT_SUBREDDITS", _DEFAULT_SUBREDDITS)
        self.subreddits = [s.strip() for s in subs.split(",") if s.strip()]
        self.limit_per_sub = int(os.environ.get("REDDIT_LIMIT_PER_SUB", _DEFAULT_LIMIT_PER_SUB))
        self.time_filter = os.environ.get("REDDIT_TIME_FILTER", _DEFAULT_TIME_FILTER)
        self.client_id = os.environ.get("REDDIT_CLIENT_ID", "")
        self.client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")
        self.username = os.environ.get("REDDIT_USERNAME", "")
        self.password = os.environ.get("REDDIT_PASSWORD", "")

    def fetch(self) -> List[RawItem]:
        if not self.client_id or not self.client_secret:
            raise RuntimeError(
                "REDDIT_CLIENT_ID 和 REDDIT_CLIENT_SECRET 环境变量为必填项。"
                "请在 https://www.reddit.com/prefs/apps 创建 script 类型应用后填入。"
            )
        if not self.username or not self.password:
            raise RuntimeError(
                "REDDIT_USERNAME 和 REDDIT_PASSWORD 环境变量为必填项（用于 script app 密码流认证）。"
            )

        user_agent = _USER_AGENT.format(username=self.username)
        reddit = praw.Reddit(
            client_id=self.client_id,
            client_secret=self.client_secret,
            username=self.username,
            password=self.password,
            user_agent=user_agent,
            timeout=self.timeout,
        )

        items: List[RawItem] = []
        for sub in self.subreddits:
            subreddit = reddit.subreddit(sub)
            for submission in subreddit.top(time_filter=self.time_filter, limit=self.limit_per_sub):
                items.append(self._to_raw_item(submission, sub))
        return items

    @staticmethod
    def _to_raw_item(submission: "praw.models.Submission", subreddit: str) -> RawItem:  # type: ignore[name-defined]
        is_self = submission.is_self
        selftext = (submission.selftext or "")[:300]
        link_url = submission.url or ""
        abstract = selftext if is_self and selftext else link_url

        created_utc = submission.created_utc or 0
        published_at = datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat() if created_utc else ""

        permalink = submission.permalink or ""
        url = f"https://www.reddit.com{permalink}" if permalink else ""

        return RawItem(
            id=f"reddit_{subreddit}_{submission.name}",
            source_name="Reddit",
            source_type="Discussion" if is_self else "Article",
            title=submission.title or "",
            abstract=abstract,
            url=url,
            published_at=published_at,
            raw_metrics={
                "score": submission.score,
                "num_comments": submission.num_comments,
                "upvote_ratio": submission.upvote_ratio,
            },
            tags=[subreddit],
            author_or_creator=str(submission.author) if submission.author else None,
        )
