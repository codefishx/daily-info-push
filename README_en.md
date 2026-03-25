# daily-info-push

English | [中文](README.md)

Fetches the latest content in parallel from 37 tech and academic sources — Hacker News, GitHub Trending, arXiv, Nature, TechCrunch, The Verge, and more — deduplicates across three layers, then uses an LLM to curate and rank the highlights into a digest pushed to Feishu (Lark) group chats. The goal is to replace manually browsing multiple feeds with a single message, helping teams stay on top of tech trends and cutting-edge research at zero effort. Fully self-contained — just configure your API keys and schedule via cron, no extra infrastructure needed.

## How It Works

```
fetch (n * adapters) → cross-source dedup → history dedup → LLM curation (LiteLLM) → merge → Feishu push
```

Three-layer deduplication: in-batch id/url/title exact match → 5-day history id/url → LLM prompt with historical titles for semantic dedup.

## Quick Start

```bash
# Install dependencies
uv sync

# Configure environment variables (copy to ~/.daily-info-push/.env)
cp .env.example ~/.daily-info-push/.env
# Edit and fill in API keys

# Dry run (no Feishu push)
uv run python main.py --date 2026-03-20 --dry-run

# Production run
uv run python main.py --date 2026-03-20

# Specify edition
uv run python main.py --date 2026-03-20 --edition morning
```

## Project Structure

```
main.py          Entry point, orchestrates the full pipeline
fetcher.py       Data fetching orchestration + deduplication
curator.py       Prompt construction + LiteLLM calls + structured output parsing
merger.py        Merge raw + curated results
pusher.py        Feishu OpenAPI push
models.py        Data models + JSONL utilities
prompt.md        Curation rules / prompt template
adapters/        37 data source adapters
```

## Data Directory (`~/.daily-info-push/`)

```
raw/        Raw fetched data ({prefix}.jsonl) + candidate digest ({prefix}_digest.md)
history/    Push records ({prefix}.jsonl), used for dedup and traceability
logs/       Fetch logs
.env        Environment variables
```

## Environment Variables

Required: `GEMINI_API_KEY`, `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, `FEISHU_CHAT_ID`

Optional: API keys and tuning parameters for individual adapters — see `.env.example`. Unconfigured sources will fail gracefully without affecting the overall pipeline.

## Scheduled Runs on Ubuntu (crontab)

The project includes a `run.sh` wrapper script that switches to the project directory (resolving `uv`'s `pyproject.toml` working directory requirement) and writes logs to `~/.daily-info-push/logs/`.

### 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc  # or ~/.profile
uv --version
```

### 2. Deploy

```bash
git clone <repo-url> ~/daily-info-push
cd ~/daily-info-push
uv sync

# Configure environment variables
mkdir -p ~/.daily-info-push
cp .env.example ~/.daily-info-push/.env
vim ~/.daily-info-push/.env
```

### 3. Verify

```bash
cd ~/daily-info-push
./run.sh morning  # Test morning edition (add --dry-run in main.py args to skip push)

# Check logs
cat ~/.daily-info-push/logs/$(date +%F)_morning.log
```

### 4. Configure crontab

Beijing time = UTC+8. 8:00 AM = UTC 0:00, 7:00 PM = UTC 11:00.

```bash
crontab -e
```

Add the following (assuming project is at `~/daily-info-push`, adjust paths accordingly):

```cron
# Ensure cron can find uv (adjust path based on `which uv` output)
PATH=/usr/local/bin:/usr/bin:/bin:/home/<user>/.local/bin:/home/<user>/.cargo/bin

# Daily morning edition — Beijing 08:00 (UTC 00:00)
0 0 * * * /home/<user>/daily-info-push/run.sh morning

# Daily evening edition — Beijing 19:00 (UTC 11:00)
0 11 * * * /home/<user>/daily-info-push/run.sh evening
```

> **Note**: Replace `<user>` with your actual username. If your server timezone is set to `Asia/Shanghai`, use Beijing time directly:
> ```cron
> 0 8 * * * /home/<user>/daily-info-push/run.sh morning
> 0 19 * * * /home/<user>/daily-info-push/run.sh evening
> ```
>
> Check/set timezone: `timedatectl` / `sudo timedatectl set-timezone Asia/Shanghai`

### Logs

Log path: `~/.daily-info-push/logs/{date}_{edition}.log`, e.g.:

```
~/.daily-info-push/logs/2026-03-20_morning.log
~/.daily-info-push/logs/2026-03-20_evening.log
```

Each run appends (`>>`) and does not overwrite previous logs.

## Dependencies

httpx (HTTP) / feedparser (RSS) / litellm (LLM API) / pydantic (structured output)

## License

[MIT](LICENSE)
