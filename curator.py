"""LLM 精选 — 构建 prompt、调用 LiteLLM、解析结构化输出。"""

from __future__ import annotations

import os
from pathlib import Path

import litellm

from models import CurationResult


def build_prompt(digest_content: str, history_titles: list[str], rules_content: str) -> str:
    """拼接完整的精选 prompt。"""
    titles_block = (
        "\n".join(f"- {t}" for t in history_titles)
        if history_titles
        else "（无历史记录）"
    )
    return f"""你是一个信息精选助手。请根据以下规则、候选摘要和历史记录，完成精选任务。

## 精选规则
{rules_content}

## 最近5天已推送标题（用于去重，不要重复推送这些内容）
{titles_block}

## 当日候选摘要
{digest_content}
"""


def curate(digest_content: str, history_titles: list[str]) -> CurationResult:
    """调用 LLM 执行精选，返回结构化结果。"""
    rules_path = Path(__file__).parent / "prompt.md"
    rules_content = rules_path.read_text(encoding="utf-8")
    prompt = build_prompt(digest_content, history_titles, rules_content)

    model = os.environ.get("LLM_MODEL", "gemini/gemini-3.1-pro-preview")
    response = litellm.completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format=CurationResult,
    )
    return CurationResult.model_validate_json(response.choices[0].message.content)


def flatten_curation(result: CurationResult) -> list[dict]:
    """将 CurationResult 展平为 curated items list（兼容 merge 的 dict 格式）。"""
    items: list[dict] = []
    for ranking_list in result.lists:
        list_id = ranking_list.list_id
        for rank, item in enumerate(ranking_list.items, start=1):
            items.append({
                "id": item.id,
                "list": list_id,
                "rank": rank,
                "abstract": item.abstract,
            })
    return items
