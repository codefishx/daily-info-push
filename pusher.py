"""飞书 OpenAPI 推送 — 获取 token、构建消息、发送到群组。"""

from __future__ import annotations

import json
import os
from collections import defaultdict

import httpx

from models import LIST_PRIORITY

# 榜单显示名映射
LIST_DISPLAY_NAMES: dict[str, str] = {
    "main": "\U0001f3c6 综合榜",
    "ai_cs": "\U0001f916 AI 和计算机榜",
    "opensource": "\U0001f4e6 开源项目榜",
    "product": "\U0001f680 产品榜",
    "business": "\U0001f4bc 商业榜",
    "economy": "\U0001f4ca 经济榜",
    "macro": "\U0001f30d 宏观榜",
    "biotech_med": "\U0001f9ec 生物科技与生理、医学榜",
    "science": "\U0001f52c 基础科学突破榜",
    "tool": "\U0001f6e0\ufe0f 实用工具榜",
    "hot": "\U0001f525 热度榜",
    "notable": "\U0001f4ce 其他值得关注榜",
}

# edition 标题映射
EDITION_TITLES: dict[str | None, str] = {
    None: "每日信息推送",
    "morning": "每日早报",
    "noon": "每日午报",
    "evening": "每日晚报",
}


def _get_tenant_token(app_id: str, app_secret: str) -> str:
    """获取飞书 tenant_access_token。"""
    resp = httpx.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/",
        json={"app_id": app_id, "app_secret": app_secret},
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取 token 失败: {data}")
    return data["tenant_access_token"]


def _send_message(token: str, chat_id: str, text: str) -> None:
    """发送文本消息到飞书群组。"""
    resp = httpx.post(
        "https://open.feishu.cn/open-apis/im/v1/messages",
        params={"receive_id_type": "chat_id"},
        headers={"Authorization": f"Bearer {token}"},
        json={
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}),
        },
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"发送消息失败: {data}")


def _list_sort_key(list_id: str) -> int:
    return LIST_PRIORITY.get(list_id, 50)


def build_message_text(
    records: list[dict],
    date_str: str,
    edition: str | None,
    failed_sources: list[str] | None = None,
) -> str:
    """将推送记录构建为飞书文本消息。"""
    display_title = EDITION_TITLES.get(edition, f"每日推送（{edition}）")
    lines: list[str] = [
        f"\U0001f4f0 {display_title} — {date_str}",
        "---------------------------------",
        "",
    ]

    # 按 list 分组
    groups: dict[str, list[dict]] = defaultdict(list)
    summary_text = ""
    for r in records:
        list_id = r.get("list", "")
        if list_id == "summary" or r.get("id") == "__summary__":
            summary_text = r.get("abstract", "")
            continue
        groups[list_id].append(r)

    # 按榜单优先级排序输出
    for list_id in sorted(groups.keys(), key=_list_sort_key):
        items = sorted(groups[list_id], key=lambda x: x.get("rank", 999))
        display_name = LIST_DISPLAY_NAMES.get(list_id, f"\U0001f4cb {list_id}")
        lines.append(display_name)
        for item in items:
            rank = item.get("rank", "")
            title = item.get("title", "")
            url = item.get("url", "")
            source = item.get("source_name", "")
            abstract = item.get("abstract", "")
            lines.append(f"{rank}. {title}")
            if url:
                lines.append(f"\U0001f517 {url}")
            lines.append(f"\U0001f4cc 来源：{source}")
            lines.append(abstract)
            lines.append("")
        lines.append("")

    # 失败源提示
    if failed_sources:
        lines.append(f"\u26a0\ufe0f 以下数据源抓取失败：{', '.join(failed_sources)}")
        lines.append("")

    # 今日小结
    lines.append("---------------------------------")
    lines.append(f"\U0001f4ac 今日小结")
    lines.append(summary_text)

    return "\n".join(lines)


def split_if_needed(text: str, max_len: int = 30000) -> list[str]:
    """在榜单边界处拆分过长的消息。"""
    if len(text.encode("utf-8")) <= max_len:
        return [text]

    all_lines = text.split("\n")
    messages: list[str] = []
    current: list[str] = []
    current_size = 0

    # 找到标题头（前3行）
    header_lines = all_lines[:3]
    body_lines = all_lines[3:]

    current = list(header_lines)
    current_size = sum(len(l.encode("utf-8")) + 1 for l in current)

    section: list[str] = []
    for line in body_lines:
        section.append(line)
        # 检测榜单边界：连续两个空行或新榜单开头
        is_section_end = (
            line == ""
            and len(section) > 1
            and section[-2] == ""
        )
        if is_section_end:
            section_size = sum(len(l.encode("utf-8")) + 1 for l in section)
            if current_size + section_size > max_len and current:
                messages.append("\n".join(current))
                # 后续消息的标题
                title_line = header_lines[0] if header_lines else ""
                continuation = title_line.replace(" — ", "（续） — ")
                current = [continuation, "---------------------------------", ""]
                current_size = sum(len(l.encode("utf-8")) + 1 for l in current)
            current.extend(section)
            current_size += section_size
            section = []

    # 剩余内容
    if section:
        current.extend(section)
    if current:
        messages.append("\n".join(current))

    return messages if messages else [text]


def push_to_lark(
    records: list[dict],
    date_str: str,
    edition: str | None,
    failed_sources: list[str] | None = None,
) -> None:
    """构建消息并推送到飞书群组。"""
    app_id = os.environ["FEISHU_APP_ID"]
    app_secret = os.environ["FEISHU_APP_SECRET"]
    chat_id = os.environ["FEISHU_CHAT_ID"]

    token = _get_tenant_token(app_id, app_secret)
    text = build_message_text(records, date_str, edition, failed_sources)
    messages = split_if_needed(text, max_len=30000)
    for msg in messages:
        _send_message(token, chat_id, msg)
