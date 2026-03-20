"""Wikipedia Current Events Portal 适配器 — 通过 MediaWiki API 获取当日新闻事件。

每个顶级事件对应一个 RawItem，类别作为 tag。支持类别白名单、优先级排序、
单类别 limit 和总 limit 配置。
"""

from __future__ import annotations

import os
import re
from datetime import date
from typing import List

import httpx

from adapters.base import BaseAdapter
from models import RawItem

_API_URL = "https://en.wikipedia.org/w/api.php"
_DEFAULT_LIMIT = 15
_DEFAULT_LIMIT_PER_CATEGORY = 2

_KNOWN_CATEGORIES = [
    "Armed conflicts and attacks",
    "Arts and culture",
    "Business and economy",
    "Disasters and accidents",
    "Health and environment",
    "International relations",
    "Law and crime",
    "Politics and elections",
    "Science and technology",
    "Sports",
]

_RE_CATEGORY = re.compile(r"'''(.+?)'''")
_RE_WIKI_LINK = re.compile(r"\[\[([^|\]]+?)(?:\|([^\]]+?))?\]\]")
_RE_EXTERNAL_URL = re.compile(r"\[(https?://\S+)\s+\(([^)]+)\)\]")
_RE_TEMPLATE = re.compile(r"\{\{[^}]*\}\}")


def _clean_wikitext(text: str) -> str:
    """Remove wiki markup, leaving plain text."""
    text = _RE_TEMPLATE.sub("", text)
    text = _RE_WIKI_LINK.sub(lambda m: m.group(2) or m.group(1), text)
    text = _RE_EXTERNAL_URL.sub(lambda m: f"({m.group(2)})", text)
    text = re.sub(r"\[https?://\S+\s*\]", "", text)
    text = re.sub(r"\[https?://\S+\]", "", text)
    return text.strip()


def _extract_first_url(lines: list[str]) -> str:
    """Extract the first external URL from event lines."""
    for line in lines:
        m = _RE_EXTERNAL_URL.search(line)
        if m:
            return m.group(1)
    for line in lines:
        m = _RE_WIKI_LINK.search(line)
        if m:
            target = m.group(1).replace(" ", "_")
            return f"https://en.wikipedia.org/wiki/{target}"
    return ""


def _extract_first_wiki_target(line: str) -> str:
    """Extract the first wiki link target for constructing a Wikipedia URL."""
    m = _RE_WIKI_LINK.search(line)
    if m:
        return m.group(1).replace(" ", "_")
    return ""


class WikipediaCurrentEventsAdapter(BaseAdapter):

    @property
    def name(self) -> str:
        return "Wikipedia Current Events"

    def __init__(self) -> None:
        self.total_limit = int(os.environ.get("WIKI_LIMIT", _DEFAULT_LIMIT))
        self.limit_per_category = int(
            os.environ.get("WIKI_LIMIT_PER_CATEGORY", _DEFAULT_LIMIT_PER_CATEGORY)
        )

        whitelist_env = os.environ.get("WIKI_CATEGORY_WHITELIST", "")
        self.category_whitelist: set[str] | None = (
            {c.strip() for c in whitelist_env.split(",") if c.strip()}
            if whitelist_env
            else None
        )

        priority_env = os.environ.get("WIKI_CATEGORY_PRIORITY", "")
        self.category_priority: list[str] = (
            [c.strip() for c in priority_env.split(",") if c.strip()]
            if priority_env
            else []
        )

    def fetch(self) -> List[RawItem]:
        today = date.today()
        page_name = f"Portal:Current_events/{today.year}_{today.strftime('%B')}_{today.day}"

        params = {
            "action": "parse",
            "page": page_name,
            "prop": "wikitext",
            "format": "json",
            "formatversion": "2",
        }
        headers = {"User-Agent": "daily-info-push/1.0 (Wikipedia-CE-Adapter)"}

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(_API_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        wikitext = data.get("parse", {}).get("wikitext", "")
        if not wikitext:
            return []

        date_str = today.isoformat()
        categorized_events = self._parse_wikitext(wikitext)
        return self._build_items(categorized_events, date_str)

    def _parse_wikitext(self, wikitext: str) -> list[tuple[str, list[list[str]]]]:
        """Parse wikitext into [(category, [[line, ...], [line, ...], ...]), ...]."""
        content_match = re.search(r"\|content=\s*\n?(.*)", wikitext, re.DOTALL)
        content = content_match.group(1) if content_match else wikitext
        content = re.sub(r"\}\}\s*$", "", content)

        lines = content.split("\n")
        categorized: list[tuple[str, list[list[str]]]] = []
        current_category = ""
        current_events: list[list[str]] = []
        current_event_lines: list[str] = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            cat_match = _RE_CATEGORY.match(line)
            if cat_match:
                if current_event_lines:
                    current_events.append(current_event_lines)
                if current_category:
                    categorized.append((current_category, current_events))
                current_category = cat_match.group(1)
                current_events = []
                current_event_lines = []
                continue

            if line.startswith("*") and not line.startswith("**"):
                if current_event_lines:
                    current_events.append(current_event_lines)
                current_event_lines = [line.lstrip("* ")]
            elif line.startswith("*"):
                current_event_lines.append(line.lstrip("* "))

        if current_event_lines:
            current_events.append(current_event_lines)
        if current_category:
            categorized.append((current_category, current_events))

        return categorized

    def _build_items(
        self,
        categorized: list[tuple[str, list[list[str]]]],
        date_str: str,
    ) -> List[RawItem]:
        if self.category_priority:
            priority_map = {c: i for i, c in enumerate(self.category_priority)}
            categorized.sort(key=lambda x: priority_map.get(x[0], len(self.category_priority)))

        items: List[RawItem] = []
        idx = 0

        for category, events in categorized:
            if self.category_whitelist and category not in self.category_whitelist:
                continue

            cat_count = 0
            for event_lines in events:
                if cat_count >= self.limit_per_category:
                    break
                if len(items) >= self.total_limit:
                    return items

                title_line = event_lines[0]
                title = _clean_wikitext(title_line)

                all_text = " ".join(_clean_wikitext(l) for l in event_lines)
                abstract = all_text[:500] if len(all_text) > 500 else all_text

                url = _extract_first_url(event_lines)
                if not url:
                    target = _extract_first_wiki_target(title_line)
                    if target:
                        url = f"https://en.wikipedia.org/wiki/{target}"

                items.append(RawItem(
                    id=f"wiki_ce_{date_str}_{idx}",
                    source_name="Wikipedia Current Events",
                    source_type="News",
                    title=title,
                    abstract=abstract,
                    url=url,
                    published_at=date_str,
                    raw_metrics={},
                    tags=[category],
                    author_or_creator=None,
                ))
                idx += 1
                cat_count += 1

        return items
