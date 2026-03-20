"""Hugging Face Daily Papers 适配器 — 获取当日精选 AI/ML 论文。"""

from __future__ import annotations

import os
from typing import List

import httpx

from adapters.base import BaseAdapter
from models import RawItem

_DEFAULT_LIMIT = 2
_API_URL = "https://huggingface.co/api/daily_papers"
_PAPER_URL = "https://huggingface.co/papers/"


class HuggingFacePapersAdapter(BaseAdapter):

    @property
    def name(self) -> str:
        return "Hugging Face Papers"

    def __init__(self) -> None:
        self.limit = int(os.environ.get("HF_PAPERS_LIMIT", _DEFAULT_LIMIT))

    def fetch(self) -> List[RawItem]:
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(_API_URL)
            resp.raise_for_status()
            data = resp.json()

        items: List[RawItem] = []
        for entry in data[: self.limit]:
            items.append(self._to_raw_item(entry))
        return items

    @staticmethod
    def _to_raw_item(entry: dict) -> RawItem:
        paper = entry.get("paper", {})
        paper_id = paper.get("id", "")
        title = paper.get("title") or entry.get("title", "")
        summary = paper.get("summary") or entry.get("summary", "")
        authors = paper.get("authors") or []
        first_author = authors[0].get("name", "") if authors else None

        return RawItem(
            id=f"hf_paper_{paper_id}",
            source_name="Hugging Face Papers",
            source_type="Paper",
            title=title,
            abstract=summary,
            url=f"{_PAPER_URL}{paper_id}",
            published_at=paper.get("publishedAt", ""),
            raw_metrics={
                "upvotes": paper.get("upvotes", 0),
                "num_comments": entry.get("numComments", 0),
                "github_stars": paper.get("githubStars"),
            },
            tags=paper.get("ai_keywords") or [],
            author_or_creator=first_author,
        )
