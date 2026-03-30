# Logseq Processor

[![Tests](https://github.com/YOUR_USERNAME/logseq-processor/actions/workflows/test.yml/badge.svg)](https://github.com/YOUR_USERNAME/logseq-processor/actions/workflows/test.yml)

Logseq article processor with tabs support, URL normalization, and rate limiting. Now with **GitHub Actions integration** for remote URL submission.

## Features

- Process tabs*.html files with multiple links
- Extract metadata using LLM
- YouTube transcript support
- Rate limiting per domain
- Log file with rotation
- Error handling with dedicated folders

## Usage

```bash
uv run logseq-processor [path] [--model MODEL] [--force] [--debug]
```

### Worker modes (pipeline split)

```bash
# Full default behavior (parallel branches in one process):
# FILE/QUEUE ingest + LLM worker run together
uv run logseq-processor [path] --worker all

# Ingestion only (watch files, parse links, expand short URLs, fetch/extract, queue LLM jobs)
uv run logseq-processor [path] --worker ingest

# LLM only (consume queued jobs and produce final Logseq notes)
uv run logseq-processor [path] --worker llm
```

`--worker all` now runs ingest and LLM branches concurrently, so file handling and summarization progress in parallel.

LLM worker parallelism is configurable via `config.yaml`:

```yaml
llm:
  max_parallel_jobs: 1  # set >1 for bounded concurrent queued_llm processing
```

### Practical tuning knobs

Use these as safe starting points, then adjust based on CPU/network pressure:

```yaml
http:
  retry_429_count: 3              # recommended: 3 (raise to 5 for noisy/rate-limited sources)
  retry_429_backoff_seconds: 1.0  # recommended: 1.0 (use 2.0 if 429s are frequent)

llm:
  max_parallel_jobs: 2            # recommended: 2 on typical desktops, keep 1 on low-RAM hosts

logging:
  queue_heartbeat_seconds: 10     # recommended: 10; use 20-30 to reduce log chatter
```

## Configuration

Edit `config.yaml` to customize settings.

## GitHub Actions Integration

Submit articles for processing via GitHub Actions without needing to run the processor locally:

### Quick Start

1. **Submit URLs** via GitHub → Actions → "Process Articles" workflow
   - Input comma-separated URLs
   - Optionally add titles and tags
   - Workflow validates and queues articles

2. **Run Local Worker** (where Ollama is available)
   ```bash
   git pull
   uv run logseq-processor --worker ingest
   uv run logseq-processor --worker llm
   ```

3. **Sync Results** back to GitHub (optional)
   - Use "Sync Processed Files" workflow, or
   - Manually: `git add articles/ queue/ && git commit && git push`

**See [docs/GITHUB_ACTIONS.md](docs/GITHUB_ACTIONS.md) for full setup guide.**

### Architecture

```
GitHub Actions (Queue URLs)
    ↓
Local Worker (Ingest + LLM processing)
    ↓
GitHub (Sync Results)
```

Key files:
- `.github/workflows/process-articles.yml` - Submit URLs
- `.github/workflows/test.yml` - Run validation tests
- `.github/workflows/sync-processed.yml` - Pull results back
- `queue/status.json` - Track processing state
- `scripts/validate_urls.py` - URL validation utility
- `scripts/queue_to_markdown.py` - Queue generation
- `scripts/check_queue.py` - Monitor queue status

## Link resolution behavior

- The resolver follows redirects with layered fallback:
  - `HEAD` with redirects
  - `GET` fallback if `HEAD` fails
  - wrapped query extraction (`url`, `u`, `target`, `redirect`, `dest`, `to`)
  - HTML fallback (`canonical`, `og:url`, meta refresh, simple JS redirects)
- Unsafe/local targets are rejected (`localhost`, private/loopback/link-local IP ranges).
- Canonical resolved URL is used for dedupe and saved as `url::` in generated notes.

## Why some one-line link files go to `errors`

A one-line file with a valid URL can still fail if the target site blocks or hides content:

- HTTP access blocked (`403`, `429`, auth-required pages)
- SSL certificate validation failure
- JS-heavy / app-style pages where static extraction returns no readable article text

This is expected for some domains and does not necessarily indicate malformed input files.
