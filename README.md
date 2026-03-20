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

## Ubuntu 定时运行（crontab）

项目提供 `run.sh` 包装脚本，自动切换到项目目录（解决 `uv` 依赖 `pyproject.toml` 的工作目录问题），并将日志写入 `~/.daily-info-push/logs/`。

### 1. 安装 uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# 安装后确认 uv 在 PATH 中
source ~/.bashrc  # 或 ~/.profile
uv --version
```

### 2. 部署项目

```bash
git clone <repo-url> ~/daily-info-push
cd ~/daily-info-push
uv sync

# 配置环境变量
mkdir -p ~/.daily-info-push
cp .env.example ~/.daily-info-push/.env
# 编辑填入 API key
vim ~/.daily-info-push/.env
```

### 3. 验证

```bash
cd ~/daily-info-push
./run.sh morning  # 测试晨报（加 --dry-run 可在 main.py 参数里控制）

# 查看日志
cat ~/.daily-info-push/logs/$(date +%F)_morning.log
```

### 4. 配置 crontab

北京时间 = UTC+8。早上 8:00 = UTC 0:00，晚上 19:00 = UTC 11:00。

```bash
crontab -e
```

添加以下内容（假设项目在 `~/daily-info-push`，根据实际路径修改）：

```cron
# 确保 cron 能找到 uv（根据 `which uv` 输出调整路径）
PATH=/usr/local/bin:/usr/bin:/bin:/home/<user>/.local/bin:/home/<user>/.cargo/bin

# 每日早报 — 北京时间 08:00 (UTC 00:00)
0 0 * * * /home/<user>/daily-info-push/run.sh morning

# 每日晚报 — 北京时间 19:00 (UTC 11:00)
0 11 * * * /home/<user>/daily-info-push/run.sh evening
```

> **注意**：将 `<user>` 替换为实际用户名。如果服务器时区已设为 `Asia/Shanghai`，则直接用北京时间：
> ```cron
> 0 8 * * * /home/<user>/daily-info-push/run.sh morning
> 0 19 * * * /home/<user>/daily-info-push/run.sh evening
> ```
>
> 查看/设置时区：`timedatectl` / `sudo timedatectl set-timezone Asia/Shanghai`

### 日志

日志路径：`~/.daily-info-push/logs/{日期}_{edition}.log`，例如：

```
~/.daily-info-push/logs/2026-03-20_morning.log
~/.daily-info-push/logs/2026-03-20_evening.log
```

每次运行会追加写入（`>>`），不会覆盖历史日志。

## 依赖

httpx (HTTP) / feedparser (RSS) / litellm (LLM API) / pydantic (结构化输出)
