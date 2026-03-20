"""合并 — 将 raw items 与 curated items 合并为完整推送记录。"""

from __future__ import annotations

import logging

from models import sort_key_for_push_record

logger = logging.getLogger()


def merge(raw_items: list[dict], curated_items: list[dict]) -> list[dict]:
    """将 raw JSONL 数据与 LLM 精选结果合并，返回排序后的推送记录列表。"""
    raw_map = {item["id"]: item for item in raw_items}
    merged: list[dict] = []

    for cur in curated_items:
        cid = cur.get("id")
        if cid == "__summary__":
            merged.append(cur)
            continue
        raw = raw_map.get(cid)
        if raw is None:
            logger.warning("curated id=%s 在 raw 中不存在，跳过", cid)
            continue
        record = dict(raw)
        record["abstract"] = cur["abstract"]
        record["list"] = cur["list"]
        record["rank"] = cur["rank"]
        merged.append(record)

    merged.sort(key=sort_key_for_push_record)
    return merged
