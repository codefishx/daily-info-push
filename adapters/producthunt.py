"""Product Hunt 适配器 — 通过 GraphQL API 获取每日最受欢迎产品。"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import List

import httpx

from adapters.base import BaseAdapter
from models import RawItem

_DEFAULT_LIMIT = 4
_GRAPHQL_URL = "https://api.producthunt.com/v2/api/graphql"

_QUERY = """
query todayPosts($postedAfter: DateTime, $postedBefore: DateTime, $first: Int!) {
  posts(
    postedAfter: $postedAfter
    postedBefore: $postedBefore
    first: $first
    order: VOTES
  ) {
    edges {
      node {
        id
        name
        tagline
        description
        url
        website
        votesCount
        commentsCount
        createdAt
        slug
        topics(first: 5) { edges { node { name } } }
      }
    }
  }
}
"""


class ProductHuntAdapter(BaseAdapter):

    @property
    def name(self) -> str:
        return "Product Hunt"

    def __init__(self) -> None:
        self.limit = int(os.environ.get("PH_LIMIT", _DEFAULT_LIMIT))
        self.token = os.environ.get("PRODUCTHUNT_TOKEN", "")

    def fetch(self) -> List[RawItem]:
        if not self.token:
            raise RuntimeError("PRODUCTHUNT_TOKEN environment variable is required")

        now = datetime.now(timezone.utc)
        past_24h = now - timedelta(hours=24)

        variables = {
            "postedAfter": past_24h.isoformat(),
            "postedBefore": now.isoformat(),
            "first": self.limit,
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                _GRAPHQL_URL,
                json={"query": _QUERY, "variables": variables},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        edges = data.get("data", {}).get("posts", {}).get("edges", [])
        items: List[RawItem] = []
        for edge in edges:
            node = edge.get("node", {})
            items.append(self._to_raw_item(node))
        return items

    @staticmethod
    def _to_raw_item(node: dict) -> RawItem:
        post_id = node.get("id", "")
        tagline = node.get("tagline", "")
        description = node.get("description", "")
        abstract = f"{tagline}. {description}" if description else tagline
        url = node.get("website") or node.get("url", "")

        topic_edges = node.get("topics", {}).get("edges", [])
        tags = [e["node"]["name"] for e in topic_edges if e.get("node", {}).get("name")]

        return RawItem(
            id=f"ph_product_{post_id}",
            source_name="Product Hunt",
            source_type="Product",
            title=node.get("name", ""),
            abstract=abstract,
            url=url,
            published_at=node.get("createdAt", ""),
            raw_metrics={
                "votes_count": node.get("votesCount", 0),
                "comments_count": node.get("commentsCount", 0),
            },
            tags=tags,
        )
