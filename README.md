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

Two ways to process articles using GitHub Actions:

### Way 1: Automatic Nextcloud Sync (Recommended)

Drop `.md` files in `~/Nextcloud/Notes/` → Auto-sync → GitHub processes → Results sync back

**Setup (one-time):**

```bash
# 1. Get GitHub token from: https://github.com/settings/tokens
# 2. Set environment variable
export GITHUB_TOKEN=ghp_XXXXXXXXXXXXXXXXXXXX

# 3. Start both scripts (in separate terminals)
Terminal 1: python scripts/sync_nextcloud_to_github.py --watch
Terminal 2: python scripts/pull_processed_articles.py --daemon
```

**Usage:**

```bash
# Create file with URL
echo "Check this: https://github.blog/article" > ~/Nextcloud/Notes/article.md

# Wait ~10 minutes...

# Check results
ls ~/Nextcloud/Notes/articles/
```

Benefits:
- ✅ Natural workflow (drop files, they process automatically)
- ✅ No GitHub UI needed
- ✅ Can batch multiple URLs via tabs*.html
- ✅ Results automatically pull back

**See [docs/SYNC_SETUP.md](docs/SYNC_SETUP.md) for detailed setup.**

### Way 2: Manual GitHub UI

Go to GitHub Actions, paste URL, click "Run" → GitHub processes → Pull results

**Usage:**

```bash
# Go to: GitHub → Actions → "Process Articles (End-to-End)"
# 1. Paste URLs: https://github.blog/article
# 2. Click "Run workflow"
# 3. Wait ~10 minutes
# 4. git pull
# 5. Check ~/Nextcloud/Notes/articles/
```

Benefits:
- ✅ Quickest for single articles
- ✅ No local setup needed
- ✅ Works from anywhere (phone, web UI)

### Architecture

```
Way 1: Automatic Sync          Way 2: Manual GitHub UI
───────────────────────────    ───────────────────────────
Nextcloud/Notes/               GitHub Actions
    ↓                          ↓
sync_nextcloud_to_github.py    (User triggers manually)
    ↓                          ↓
GitHub API → GitHub Actions    GitHub Actions
    ↓                          ↓
process-articles workflow      process-articles workflow
(with Docker Ollama)           (with Docker Ollama)
    ↓                          ↓
git push to repo               git push to repo
    ↓                          ↓
pull_processed_articles.py     git pull
    ↓                          ↓
Nextcloud/Notes/articles/      Nextcloud/Notes/articles/
```

**Key files:**
- `scripts/sync_nextcloud_to_github.py` - Way 1 watch & sync
- `scripts/pull_processed_articles.py` - Way 1 pull results
- `.github/workflows/process-articles.yml` - End-to-end processing
- `.github/workflows/test.yml` - Run validation tests
- `docs/SYNC_SETUP.md` - Detailed setup guide for Way 1
- `docs/GITHUB_ACTIONS.md` - Complete GitHub Actions documentation

**Choose your workflow:**

| Feature | Way 1 (Auto) | Way 2 (Manual) |
|---------|--------------|----------------|
| Nextcloud integration | ✅ Native | ✅ Via git pull |
| Auto-detection | ✅ File watcher | ✗ Manual |
| Setup complexity | Medium (2 scripts) | Low (none) |
| Best for | Batch processing | Single articles |
| Works from phone | ✗ | ✅ |
| Requires local daemon | ✅ (2 terminals) | ✗ |

**Quick start guide:**

1. For **Way 1** → See [docs/SYNC_SETUP.md](docs/SYNC_SETUP.md)
2. For **Way 2** → Go to GitHub Actions UI, click "Process Articles (End-to-End)", fill form
3. For **full details** → See [docs/GITHUB_ACTIONS.md](docs/GITHUB_ACTIONS.md)

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
