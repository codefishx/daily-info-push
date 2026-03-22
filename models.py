"""数据实体定义与 JSONL 序列化工具。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel


@dataclass
class RawItem:
    """原始数据实体 — 各数据源产出的统一格式。"""

    id: str
    source_name: str
    source_type: str
    title: str
    abstract: str
    url: str
    published_at: str
    raw_metrics: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    author_or_creator: Optional[str] = None

    VALID_SOURCE_TYPES = frozenset(
        ["Repository", "Article", "Paper", "News", "Discussion", "Tool", "Product"]
    )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d = {k: v for k, v in d.items() if v is not None}
        return d


@dataclass
class CuratedItem:
    """精选实体 — LLM 输出的精选结果。"""

    id: str
    list: str
    rank: int
    abstract: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PushRecordItem:
    """推送记录实体 — raw + curated 合并后的完整记录。"""

    id: str
    source_name: str
    source_type: str
    title: str
    abstract: str
    url: str
    published_at: str
    list: str
    rank: int
    raw_metrics: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    author_or_creator: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d = {k: v for k, v in d.items() if v is not None}
        return d


# ---------------------------------------------------------------------------
# JSONL 工具函数
# ---------------------------------------------------------------------------

LIST_PRIORITY = {
    "main": 0,
    "ai_cs": 1,
    "opensource": 2,
    "product": 3,
    "business": 4,
    "economy": 5,
    "macro": 6,
    "biotech_med": 7,
    "science": 8,
    "tool": 9,
    "hot": 10,
    "notable": 11,
    "summary": 99,
}


def to_jsonl_line(obj: dict[str, Any] | RawItem | CuratedItem | PushRecordItem) -> str:
    """将对象序列化为一行 JSON 字符串（不含换行符）。"""
    d = obj.to_dict() if hasattr(obj, "to_dict") else obj
    return json.dumps(d, ensure_ascii=False)


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """读取 JSONL 文件，返回 dict 列表。跳过空行。"""
    items: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def write_jsonl(path: str | Path, items: list[dict[str, Any] | RawItem | CuratedItem | PushRecordItem]) -> None:
    """将对象列表写入 JSONL 文件。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for item in items:
            f.write(to_jsonl_line(item) + "\n")


def sort_key_for_push_record(item: dict[str, Any]) -> tuple[int, int]:
    """按榜单优先级 + rank 排序。"""
    priority = LIST_PRIORITY.get(item.get("list", ""), 99)
    return (priority, item.get("rank", 999))


def make_run_prefix(date_str: str, edition: str | None = None) -> str:
    """生成运行前缀，用于构建文件名。

    无 edition 时返回 '{date}'，有 edition 时返回 '{date}_{edition}'。
    兼容旧的纯日期文件名格式。
    """
    if edition:
        return f"{date_str}_{edition}"
    return date_str


def find_history_files(history_dir: str | Path, before_date: str, days: int = 5) -> list[Path]:
    """自动查找 history_dir 下最近 days 天内的所有 JSONL 文件（支持多 edition）。

    从 before_date（含）往前推 days 天，匹配文件名前 10 个字符为日期的所有 JSONL 文件。
    兼容 '{date}.jsonl' 和 '{date}_{edition}.jsonl' 两种格式。
    """
    from datetime import date, timedelta

    history_dir = Path(history_dir)
    if not history_dir.is_dir():
        return []

    end = date.fromisoformat(before_date)
    start = end - timedelta(days=days - 1)
    valid_dates = {(start + timedelta(days=i)).isoformat() for i in range(days)}

    result: list[Path] = []
    for f in sorted(history_dir.glob("*.jsonl")):
        file_date = f.stem[:10]
        if file_date in valid_dates:
            result.append(f)
    return result


def find_all_history_files(history_dir: str | Path, before_date: str) -> list[Path]:
    """查找 history_dir 下 before_date 之前（不含当天）的所有 JSONL 文件。

    用于程序判定去重，加载全部历史记录。
    """
    from datetime import date

    history_dir = Path(history_dir)
    if not history_dir.is_dir():
        return []

    cutoff = date.fromisoformat(before_date)
    result: list[Path] = []
    for f in sorted(history_dir.glob("*.jsonl")):
        file_date = f.stem[:10]
        try:
            if date.fromisoformat(file_date) < cutoff:
                result.append(f)
        except ValueError:
            continue
    return result


def load_history_titles(history_dir: str | Path, before_date: str, days: int = 5) -> list[tuple[str, str]]:
    """从最近 days 天的历史 JSONL 文件中提取已推送的标题和摘要，用于 LLM 语义去重。

    返回 [(title, abstract), ...] 列表，abstract 为 LLM 生成的中文摘要。
    """
    paths = find_history_files(history_dir, before_date, days)
    results: list[tuple[str, str]] = []
    for p in paths:
        try:
            for item in read_jsonl(p):
                if "title" in item:
                    results.append((item["title"], item.get("abstract", "")))
        except Exception:
            continue
    return results


def load_history_ids(paths: list[str | Path]) -> tuple[set[str], set[str]]:
    """从多个历史 JSONL 文件中提取已推送的 id 和 url 集合，用于去重。

    返回 (seen_ids, seen_urls)。文件不存在或解析失败的行会被静默跳过。
    """
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    for p in paths:
        p = Path(p)
        if not p.is_file():
            continue
        try:
            for item in read_jsonl(p):
                if "id" in item:
                    seen_ids.add(item["id"])
                if item.get("url"):
                    seen_urls.add(item["url"])
        except Exception:
            continue
    return seen_ids, seen_urls


# ---------------------------------------------------------------------------
# LLM 结构化输出模型（Pydantic）
# ---------------------------------------------------------------------------


class CuratedItemOutput(BaseModel):
    """LLM 输出的单条精选结果。"""

    id: str
    abstract: str


class RankingList(BaseModel):
    """LLM 输出的单个榜单。"""

    list_name: str
    list_id: str
    items: list[CuratedItemOutput]


class CurationResult(BaseModel):
    """LLM 输出的完整精选结果。"""

    lists: list[RankingList]
