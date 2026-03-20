# daily-info-push

自包含的每日信息推送脚本。从 26 个数据源抓取 → LLM 精选排榜 → 飞书群推送。

## 流程

```
fetch (n * adapters) → 跨源去重 → 历史去重 → LLM 精选 (LiteLLM) → 合并 → 飞书推送
```

三层去重：批次内 id/url/title 精确匹配 → 5 天历史 id/url → LLM prompt 注入历史标题做语义去重。

## 快速开始

```bash
# 安装依赖
uv sync

# 配置环境变量（复制到 ~/.daily-info-push/.env）
cp .env.example ~/.daily-info-push/.env
# 编辑填入 API key

# 试运行（不推送飞书）
uv run python main.py --date 2026-03-20 --dry-run

# 正式运行
uv run python main.py --date 2026-03-20

# 指定期号
uv run python main.py --date 2026-03-20 --edition morning
```

## 目录结构

```
main.py          入口，串联全流程
fetcher.py       数据抓取编排 + 去重
curator.py       Prompt 构建 + LiteLLM 调用 + 结构化输出解析
merger.py        raw + curated 合并
pusher.py        飞书 OpenAPI 推送
models.py        数据模型 + JSONL 工具
prompt.md        精选规则/prompt 模板
adapters/        26 个数据源适配器
```

## 数据目录 (`~/.daily-info-push/`)

```
raw/        原始抓取数据 ({prefix}.jsonl) + 候选摘要 ({prefix}_digest.md)
history/    推送记录 ({prefix}.jsonl)，用于去重和回溯
logs/       抓取日志
.env        环境变量
```

## 环境变量

必填：`GEMINI_API_KEY`、`FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_CHAT_ID`

可选：各适配器的 API key 和参数调节，详见 `.env.example`。未配置的数据源会抓取失败但不影响整体流程。

## 依赖

httpx (HTTP) / feedparser (RSS) / litellm (LLM API) / pydantic (结构化输出)
