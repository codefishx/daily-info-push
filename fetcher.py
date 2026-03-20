"""数据抓取编排 — 遍历适配器、去重、写入 raw JSONL 和 digest。"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from pathlib import Path

from adapters import ADAPTERS
from models import (
    RawItem,
    find_history_files,
    load_history_ids,
    make_run_prefix,
    write_jsonl,
)

logger = logging.getLogger()

ABSTRACT_MAX_LEN = 200


def _format_metrics(raw_metrics: dict[str, object]) -> str:
    if not raw_metrics:
        return ""
    parts = [f"{k}={v}" for k, v in raw_metrics.items() if isinstance(v, (int, float))]
    return ", ".join(parts)


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _generate_digest(items: list[RawItem], digest_path: Path, date_str: str) -> None:
    """生成按源分组的 markdown digest，供 LLM 精选使用。"""
    groups: dict[str, list[RawItem]] = defaultdict(list)
    for item in items:
        groups[item.source_name].append(item)

    lines: list[str] = [f"# 候选摘要 {date_str} — 共 {len(items)} 条\n"]

    for source, group in groups.items():
        lines.append(f"## {source} — {len(group)} 条\n")
        for it in group:
            metrics = _format_metrics(it.raw_metrics)
            tags = it.tags or []
            tag_str = f" [{', '.join(tags)}]" if tags else ""
            abstract = _truncate(it.abstract, ABSTRACT_MAX_LEN)
            abstract_part = f" — {abstract}" if abstract else ""
            metrics_part = f" {metrics}" if metrics else ""
            lines.append(
                f"- `{it.id}` **{it.title}** ({it.source_type})"
                f"{metrics_part}{tag_str}{abstract_part}"
            )
        lines.append("")

    digest_path.parent.mkdir(parents=True, exist_ok=True)
    digest_path.write_text("\n".join(lines), encoding="utf-8")


def fetch_all(
    date_str: str,
    edition: str | None,
    data_dir: Path,
    history_days: int = 5,
) -> tuple[list[RawItem], list[str]]:
    """抓取所有数据源并去重，返回 (去重后的 items, 失败的数据源列表)。

    同时写入 raw JSONL 和 digest markdown 到 data_dir。
    """
    prefix = make_run_prefix(date_str, edition)
    raw_path = data_dir / "raw" / f"{prefix}.jsonl"
    digest_path = data_dir / "raw" / f"{prefix}_digest.md"

    edition_info = f" edition={edition}" if edition else ""
    logger.info("开始抓取 date=%s%s data_dir=%s", date_str, edition_info, data_dir)

    all_items: list[RawItem] = []
    source_counts: dict[str, int] = {}
    failed_sources: list[str] = []

    for adapter in ADAPTERS:
        t0 = time.time()
        try:
            items = adapter.fetch_with_retry()
            elapsed = time.time() - t0
            logger.info("[%s] 成功 — %d 条, 耗时 %.2fs", adapter.name, len(items), elapsed)
            source_counts[adapter.name] = len(items)
            all_items.extend(items)
        except Exception:
            elapsed = time.time() - t0
            logger.exception("[%s] 失败 — 耗时 %.2fs", adapter.name, elapsed)
            failed_sources.append(adapter.name)

    if not all_items:
        logger.warning("所有适配器均未返回数据")
        return [], failed_sources

    # 第一层：同批次跨源去重（id / url / title）
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    unique_items: list[RawItem] = []
    for item in all_items:
        if item.id in seen_ids:
            continue
        if item.url and item.url in seen_urls:
            continue
        normalized_title = item.title.strip().lower()
        if normalized_title and normalized_title in seen_titles:
            continue
        seen_ids.add(item.id)
        if item.url:
            seen_urls.add(item.url)
        if normalized_title:
            seen_titles.add(normalized_title)
        unique_items.append(item)

    cross_source_dedup = len(all_items) - len(unique_items)
    if cross_source_dedup:
        logger.info("跨源去重移除 %d 条（剩余 %d 条）", cross_source_dedup, len(unique_items))
    all_items = unique_items

    # 第二层：历史去重（id / url）
    dedup_count = 0
    history_paths = find_history_files(data_dir / "history", date_str, days=history_days)
    if history_paths:
        logger.info("自动发现 %d 个历史文件", len(history_paths))
        hist_ids, hist_urls = load_history_ids(history_paths)
        logger.info(
            "加载历史去重集合: %d 个 id, %d 个 url (来自 %d 个文件)",
            len(hist_ids), len(hist_urls), len(history_paths),
        )
        before = len(all_items)
        all_items = [
            item for item in all_items
            if item.id not in hist_ids
            and (not item.url or item.url not in hist_urls)
        ]
        dedup_count = before - len(all_items)
        if dedup_count:
            logger.info("历史去重移除 %d 条（剩余 %d 条）", dedup_count, len(all_items))

    if not all_items:
        logger.warning("去重后无剩余数据")
        return [], failed_sources

    # 写入 raw JSONL 和 digest
    write_jsonl(raw_path, all_items)
    digest_label = f"{date_str} ({edition})" if edition else date_str
    _generate_digest(all_items, digest_path, digest_label)

    logger.info(
        "抓取完成: 总计 %d 条, 跨源去重 %d, 历史去重 %d, 失败源 %d",
        len(all_items), cross_source_dedup, dedup_count, len(failed_sources),
    )

    return all_items, failed_sources
