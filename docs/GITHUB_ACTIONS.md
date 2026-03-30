# Logseq Processor - GitHub Actions Integration Guide

This guide explains how to use GitHub Actions to submit articles for processing, and how to set up the local worker for LLM processing.

## Overview

The logseq-processor now supports a **two-part workflow** for article processing:

1. **GitHub Actions** → Submit and validate URLs
2. **Local Worker** → Process content with Ollama LLM

This separation allows you to:
- Submit articles from anywhere (GitHub UI)
- Process them locally where Ollama is available
- Keep results synchronized via Git

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     GitHub Actions                               │
│                                                                  │
│  1. Process Articles Workflow                                    │
│     - Accept URL input (batch)                                   │
│     - Validate URLs (regex + HTTP HEAD)                          │
│     - Generate queue files (queue/pending_*.md)                  │
│     - Commit to main branch                                      │
└──────────────────┬───────────────────────────────────────────────┘
                   │
                   ↓ (Git pull)
┌──────────────────────────────────────────────────────────────────┐
│                     Local Environment                            │
│                                                                  │
│  2. Ingest Worker                                                │
│     uv run logseq-processor --worker ingest                      │
│     - Monitors queue/ folder                                     │
│     - Extracts content from URLs                                 │
│     - Queues articles for LLM processing                         │
│                                                                  │
│  3. LLM Worker                                                   │
│     uv run logseq-processor --worker llm                         │
│     - Consumes queued articles                                   │
│     - Extracts metadata (title, tags, summary) via Ollama        │
│     - Generates final Logseq markdown                            │
│     - Saves to articles/ folder                                  │
└──────────────────┬───────────────────────────────────────────────┘
                   │
                   ↓ (Git push)
┌──────────────────────────────────────────────────────────────────┐
│                 GitHub (Results Repository)                      │
│                                                                  │
│  4. Sync Processed Workflow                                      │
│     - Pulls processed articles back                              │
│     - Updates queue/status.json                                  │
│     - Commits results                                            │
└──────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Submit Articles via GitHub Actions

Go to **GitHub Repository → Actions → Process Articles** and click **"Run workflow"**.

**Inputs:**
- **URLs** (required): `https://example.com,https://other.com/article`
- **Titles** (optional): `Example Article,Other Article`
- **Tags** (optional): `python,ai,tutorial`
- **Force** (optional): Reprocess even if already done
- **Check Reachable** (optional): Validate URL availability

**Example:**
```
URLs: https://github.com/status,https://openai.com/research
Titles: GitHub Status,OpenAI Research
Tags: github,ai
Check Reachable: true
```

The workflow will:
1. ✓ Validate URLs
2. ✓ Create queue files in `queue/pending_*.md`
3. ✓ Update `queue/status.json`
4. ✓ Commit to main branch

### 2. Run Local Worker

On your machine with Ollama installed:

```bash
# Clone/pull the latest
git clone https://github.com/YOUR_REPO/logseq-processor.git
cd logseq-processor
git pull

# Install dependencies
uv sync

# Run ingest worker (extract content)
uv run logseq-processor --worker ingest

# Run LLM worker (generate metadata)
uv run logseq-processor --worker llm
```

Or run both in parallel (one terminal for each):
```bash
# Terminal 1: Ingest
uv run logseq-processor --worker ingest

# Terminal 2: LLM
uv run logseq-processor --worker llm
```

### 3. Check Queue Status

```bash
# Show full queue status
python scripts/check_queue.py

# Show summary only
python scripts/check_queue.py --summary

# Show pending items
python scripts/check_queue.py --pending

# Show errors
python scripts/check_queue.py --errors
```

### 4. Sync Results Back to GitHub

Once processing is complete:

```bash
# Push results
git add articles/ queue/
git commit -m "Processed articles"
git push origin main
```

Or use the GitHub Actions workflow:
Go to **Actions → Sync Processed Files → Run workflow**

## Queue Status

The `queue/status.json` file tracks processing state:

```json
{
  "queued": [
    {
      "url": "https://example.com",
      "file": "pending_20260330_114147_example.com_c984d06a.md",
      "title": "Example",
      "queued_at": "2026-03-30T11:41:47.884222+00:00"
    }
  ],
  "processing": [],
  "done": [
    {
      "url": "https://example.com",
      "file": "articles/example-article-20260330.md",
      "completed_at": "2026-03-30T12:00:00+00:00"
    }
  ],
  "error": [],
  "stats": {
    "total_queued": 1,
    "total_processed": 1,
    "total_errors": 0
  }
}
```

**States:**
- `queued`: Submitted but not yet processed
- `processing`: Currently being processed
- `done`: Successfully completed
- `error`: Failed processing

## Queue Files

Queue files are created in `queue/pending_*.md` with the following format:

```
url:: https://example.com
queued_at:: 2026-03-30T11:41:47.884222+00:00
title:: Example Article
tags:: python,ai
force:: false
```

The local worker reads these files and processes them in order. Once processed, the metadata is added and the final article is moved to the `articles/` folder.

## Configuration

Edit `config.yaml` to customize behavior:

```yaml
# LLM Model
model: qwen3.5:9b

# Rate Limiting
rate_limit:
  delay_per_domain: 2        # Seconds between requests to same domain
  delay_global: 1            # Global rate limit

# HTTP Retries
http:
  retry_429_count: 3         # Retry count for rate-limited responses
  retry_429_backoff_seconds: 1.0

# LLM Processing
llm:
  timeout_seconds: 120       # LLM request timeout
  max_parallel_jobs: 1       # 1 = sequential, 2+ = parallel (if RAM permits)

# Folders
folders:
  articles: articles         # Final processed articles
  errors: errors             # Failed processing
  other: Other               # Unsupported files
```

For GitHub Actions:
- Use relative paths in `watch_folder` to avoid hardcoding paths
- Example: `watch_folder: queue` to monitor the queue folder

## Worker Modes

### Ingest Worker
```bash
uv run logseq-processor --worker ingest
```

- Watches `queue/` folder for new files
- Extracts content from URLs (HTML parsing, YouTube transcripts)
- Queues articles for LLM processing
- Moves processed inputs to `processed/` folder

### LLM Worker
```bash
uv run logseq-processor --worker llm
```

- Consumes queued articles from internal queue
- Extracts metadata via Ollama LLM:
  - Title
  - Tags
  - Summary
  - Category
- Generates final Logseq markdown
- Saves to `articles/` folder
- Updates `queue/status.json`

### Both (Default)
```bash
uv run logseq-processor
```

Runs ingest and LLM workers in parallel (experimental).

## Troubleshooting

### "Connection refused" when running worker

**Problem**: Ollama service not running.

**Solution**:
```bash
# Start Ollama
ollama serve

# In another terminal, verify model is available
ollama list

# If needed, pull the model
ollama pull qwen3.5:9b
```

### URLs not queuing

**Problem**: GitHub Actions workflow failed.

**Solution**:
1. Check the GitHub Actions run logs
2. Look for validation errors in the workflow output
3. Verify URL format: should be valid HTTP(S) URLs
4. Try manual queue: `python scripts/queue_to_markdown.py "https://example.com"`

### Articles not appearing in `articles/` folder

**Problem**: LLM worker not processing queued items.

**Solution**:
1. Check queue status: `python scripts/check_queue.py --pending`
2. Run LLM worker in debug mode: `uv run logseq-processor --debug --worker llm`
3. Check Ollama logs: `ollama logs`
4. Verify model can respond: `ollama run qwen3.5:9b "test"`

### Articles stuck in `processing` state

**Problem**: LLM worker crashed or lost connection.

**Solution**:
1. Check `queue/status.json` for items in `processing` state
2. Restart the LLM worker: `uv run logseq-processor --worker llm`
3. If still stuck, manually reset status (edit `queue/status.json`)

## Advanced Topics

### Batch Processing

Submit multiple URLs at once:
```bash
python scripts/queue_to_markdown.py \
  "https://example.com,https://github.com,https://openai.com" \
  --titles="Example,GitHub,OpenAI" \
  --tags="ai,research"
```

Or use the GitHub Actions workflow with comma-separated input.

### URL Validation

Validate URLs before queuing:
```bash
python scripts/validate_urls.py \
  "https://example.com" \
  "https://github.com" \
  --check-reachable
```

### Parallel LLM Processing

For faster processing with multiple CPU cores and sufficient RAM:

```yaml
# In config.yaml
llm:
  max_parallel_jobs: 4  # Adjust based on your system
```

### Custom Titles and Tags

Override automatic extraction:
```bash
python scripts/queue_to_markdown.py \
  "https://example.com" \
  --titles="My Custom Title" \
  --tags="ai,research,important"
```

## GitHub Actions Workflows

### process-articles.yml

**Manual trigger**: Submits URLs to the queue.

**Inputs**:
- `urls`: Comma-separated URLs
- `titles`: Optional comma-separated titles
- `tags`: Optional comma-separated tags
- `force`: Reprocess flag
- `check_reachable`: Validate URLs

**Output**: Queue files created, status.json updated, commit pushed

### test.yml

**Trigger**: On push to main/develop, on pull requests.

**Checks**:
- Project structure validation
- Dependency availability
- Script functionality
- Python syntax

**Matrix**: Python 3.11, 3.12, 3.13

### sync-processed.yml

**Manual trigger**: Pulls processed articles from local worker back to GitHub.

**Actions**:
- Fetches latest from origin
- Checks for new articles
- Updates queue/status.json
- Commits results

## File Structure

```
logseq-processor/
├── .github/workflows/
│   ├── process-articles.yml    # Submit URLs
│   ├── test.yml                # Test & validation
│   └── sync-processed.yml      # Sync results back
├── queue/                      # GitHub Actions queue
│   ├── status.json             # Queue state tracking
│   └── pending_*.md            # Queued articles (generated)
├── articles/                   # Final processed articles
├── errors/                     # Failed processing
├── scripts/
│   ├── validate_urls.py        # URL validation utility
│   ├── queue_to_markdown.py    # Queue generation utility
│   └── check_queue.py          # Queue status monitoring
├── src/
│   └── main.py                 # Main processor
├── config.yaml                 # Configuration
└── docs/
    └── GITHUB_ACTIONS.md       # This file
```

## Examples

### Example 1: Submit Single Article

```
Workflow: Process Articles
URLs: https://github.blog/2024-01-new-features/
Titles: GitHub Latest Features
Tags: github,news
```

Result: One queue file created, processed by local worker.

### Example 2: Batch Research Papers

```
URLs: https://arxiv.org/abs/2310.01234,https://arxiv.org/abs/2311.05678,https://arxiv.org/abs/2312.09999
Titles: Transformer Architecture,Attention Mechanisms,Vision Transformers
Tags: ml,research,academic
```

Result: Three queue files created, processed in parallel.

### Example 3: Reprocess with Force Flag

```
URLs: https://example.com/article
Force: true
```

Result: Article reprocessed even if already in articles/ folder.

## Performance Tips

1. **Ingest Worker**: Can be always-running to watch for new queue files
2. **LLM Worker**: Start when you have queue items; adjust `max_parallel_jobs` based on system
3. **Batch Submission**: Submit 5-10 URLs at a time for efficiency
4. **Ollama Model**: Larger models = better quality but slower
   - `qwen3.5:9b`: Good balance of speed and quality
   - Try `mistral:7b` for faster, lighter processing

## Security Considerations

1. **URL Validation**: The workflow validates URLs with regex and optional HTTP HEAD check
2. **Secrets**: If your Ollama requires auth, use GitHub Secrets (not yet implemented)
3. **Rate Limiting**: Respects per-domain and global rate limits in config
4. **SSL/TLS**: Validates certificates; self-signed certs may be rejected

## Contributing & Feedback

See the main README for contributing guidelines.

For questions or issues with GitHub Actions integration:
- Check the workflow logs
- Review `queue/status.json` for processing state
- Check local logs: `~/.logseq-processor/logs/processor.log`
