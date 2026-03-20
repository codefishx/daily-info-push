"""daily-info-push 入口 — 串联抓取、精选、合并、推送全流程。"""

from __future__ import annotations

import argparse
import logging
import os
from datetime import date
from pathlib import Path

from models import load_history_titles, make_run_prefix, read_jsonl, write_jsonl

logger = logging.getLogger()


# ---------------------------------------------------------------------------
# 环境变量加载
# ---------------------------------------------------------------------------


def _load_env_file(path: Path) -> None:
    """加载单个 .env 文件，不覆盖已有的环境变量。"""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip("\"'"))


def _load_env() -> None:
    """按优先级加载 .env：系统环境变量 > ~/.daily-info-push/.env > 本目录 .env。

    先加载本目录的，再加载 home 下的。因为用 setdefault，后加载的不会覆盖先加载的。
    所以实际优先级：系统环境变量 > home/.env > 本目录/.env。
    """
    _load_env_file(Path.home() / ".daily-info-push" / ".env")
    _load_env_file(Path(__file__).parent / ".env")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="每日信息推送 — 抓取、精选、推送一体化")
    parser.add_argument("--date", default=date.today().isoformat(), help="日期 (YYYY-MM-DD)")
    parser.add_argument("--edition", default=None, help="期号（morning/noon/evening）")
    parser.add_argument("--dry-run", action="store_true", help="仅抓取和精选，不推送飞书")
    return parser.parse_args()


def main() -> None:
    _load_env()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    args = parse_args()
    data_dir = Path(
        os.environ.get("DAILY_PUSH_DATA_DIR", str(Path.home() / ".daily-info-push"))
    ).expanduser()
    prefix = make_run_prefix(args.date, args.edition)

    # 延迟导入，确保环境变量已加载
    from curator import curate, flatten_curation
    from fetcher import fetch_all
    from merger import merge
    from pusher import push_to_lark

    # 1. 抓取 + 去重
    logger.info("Step 1: 开始抓取数据")
    items, failed_sources = fetch_all(args.date, args.edition, data_dir)
    if not items:
        print("今日无数据")
        return

    # 2. LLM 精选
    logger.info("Step 2: 开始 LLM 精选")
    digest_path = data_dir / "raw" / f"{prefix}_digest.md"
    digest = digest_path.read_text(encoding="utf-8")
    history_titles = load_history_titles(data_dir / "history", args.date)
    result = curate(digest, history_titles)
    curated_items = flatten_curation(result)
    if not curated_items:
        print("LLM 未返回精选结果")
        return

    # 3. 合并 → 写入 history
    logger.info("Step 3: 合并 raw + curated")
    raw_path = data_dir / "raw" / f"{prefix}.jsonl"
    raw_items = read_jsonl(raw_path)
    records = merge(raw_items, curated_items)
    history_path = data_dir / "history" / f"{prefix}.jsonl"
    write_jsonl(history_path, records)

    # 4. 推送飞书
    if not args.dry_run:
        logger.info("Step 4: 推送飞书")
        push_to_lark(records, args.date, args.edition, failed_sources)
    else:
        logger.info("Step 4: dry-run 模式，跳过飞书推送")

    print(f"完成: {len(records)} 条记录已写入 {history_path}")


if __name__ == "__main__":
    main()
