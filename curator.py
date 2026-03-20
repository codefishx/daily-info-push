"""LLM 精选 — 构建 prompt、调用 LiteLLM、解析结构化输出。"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import litellm

from models import CurationResult

logger = logging.getLogger()


class CurationValidationError(Exception):
    """LLM 输出数据质量校验失败。"""
    pass


def validate_curation(result: CurationResult, valid_ids: set[str]) -> None:
    """校验 LLM 输出质量，不通过则抛出 CurationValidationError。"""
    errors = []
    seen_ids = set()
    for ranking_list in result.lists:
        for item in ranking_list.items:
            if item.id == "__summary__":
                continue
            if item.id not in valid_ids:
                errors.append(f"幽灵 ID: {item.id}")
            if item.id in seen_ids:
                errors.append(f"重复 ID: {item.id}")
            seen_ids.add(item.id)
    # 检查综合榜条目数
    main_lists = [l for l in result.lists if l.list_id == "main"]
    if main_lists and len(main_lists[0].items) < 5:
        errors.append(f"综合榜仅 {len(main_lists[0].items)} 条，低于最低要求 5 条")
    if errors:
        raise CurationValidationError("; ".join(errors))


def build_prompt(digest_content: str, history_titles: list[str], rules_content: str) -> str:
    """拼接完整的精选 prompt。"""
    titles_block = (
        "\n".join(f"- {t}" for t in history_titles)
        if history_titles
        else "（无历史记录）"
    )
    return f"""# 任务

你是一个信息精选助手。请从当日候选内容中精选最值得关注的内容，按榜单组织，并为每条生成中文摘要。

候选内容中每条 item 以 `[数字]` 标记唯一 ID（如 `[3]` 表示 id 为 `"3"`）。输出时 `id` 必须精确引用这些数字。

# 精选规则

{rules_content}

# 历史记录

以下是最近 5 天已推送的标题，用于语义去重，避免重复推送相同或高度相似的内容：

{titles_block}

# 当日候选内容

{digest_content}"""


def curate(
    digest_content: str,
    history_titles: list[str],
    num_to_orig: dict[str, str],
    valid_ids: set[str],
) -> CurationResult:
    """调用 LLM 执行精选，返回结构化结果。带退避重试（最多 3 次）。"""
    rules_path = Path(__file__).parent / "prompt.md"
    rules_content = rules_path.read_text(encoding="utf-8")
    prompt = build_prompt(digest_content, history_titles, rules_content)

    model = os.environ.get("LLM_MODEL", "gemini/gemini-3.1-pro-preview")
    max_retries = 3
    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("LLM 调用 (第 %d 次)", attempt)
            response = litellm.completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format=CurationResult,
            )

            # 优化 5: 记录 token 用量
            if hasattr(response, "usage") and response.usage:
                logger.info(
                    "LLM token 用量: prompt=%d, completion=%d, total=%d",
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                    response.usage.total_tokens,
                )

            result = CurationResult.model_validate_json(response.choices[0].message.content)

            # 优化 4b: 恢复原始 ID（先用数字 ID 做校验）
            validate_curation(result, set(num_to_orig.keys()))

            for ranking_list in result.lists:
                for item in ranking_list.items:
                    if item.id in num_to_orig:
                        item.id = num_to_orig[item.id]

            # 优化 3: 恢复 ID 后用原始 ID 做最终校验
            validate_curation(result, valid_ids | {"__summary__"})

            return result

        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                backoff = 2 ** attempt
                logger.warning(
                    "LLM 精选失败 (第 %d 次): %s — %ds 后重试",
                    attempt, e, backoff,
                )
                time.sleep(backoff)
            else:
                logger.error("LLM 精选失败 (第 %d 次，已耗尽重试): %s", attempt, e)

    raise last_exc  # type: ignore[misc]


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
