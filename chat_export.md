# Logseq Processor - Chat Export

Date: 2026-03-22

## Project Overview

A Python-based Logseq article processor that:
- Processes tabs*.html files with multiple links
- Extracts metadata using LLM (Ollama)
- Supports YouTube transcripts
- Rate limits requests per domain
- Organizes files into categorized folders

## Folder Structure

```
~/Nextcloud/Notes/
├── (incoming files)
├── articles/      # Processed Logseq pages
├── originals/     # Original source files (backup)
├── processed/     # Successfully processed files (deprecated)
├── errors/       # Files with issues
└── Other/        # Non-article files
```

## Configuration (config.yaml)

```yaml
model: qwen3.5:9b
default_delay_seconds: 2
max_retries: 3
warmup_llm: true

watch_folder: ~/Nextcloud/Notes

rate_limit:
  delay_per_domain: 2
  delay_global: 1

content:
  min_length: 100
  max_length: 8000

llm:
  timeout_seconds: 120
  temperature_attempts:
    - 0.05
    - 0.25
    - 0.50

folders:
  articles: articles
  processed: processed
  originals: originals
  errors: errors
  other: Other

logging:
  level: INFO
  folder: ~/.logseq-processor/logs
  retention_days: 7
  console: true
```

## Key Features Implemented

### 1. File Routing
| File Type | Success | Error |
|-----------|---------|-------|
| tabs*.html | originals/ | errors/ |
| .md with URL | originals/ | errors/ |
| .md no URL | errors/ | - |
| .md empty | errors/ | - |
| .md long | stays (skipped) | - |
| .html | originals/ | - |
| other | Other/ | - |

### 2. Queue System for tabs
- Persistent queue saved to `~/.logseq-processor/queue.json`
- Resume on interrupt
- Progress tracking

### 3. URL Normalization
- Removes www. prefix
- Removes trailing slashes
- Keeps query params: v, p, id, q, search

### 4. Domain Rate Limiting
- Configurable delay per domain
- Global minimum delay between requests

### 5. LLM Warmup
- Pre-loads model before processing
- Prevents initial timeout issues

### 6. Article Filename Format
- Format: `{domain}-{title}.md`
- Example: `fyne.io-Fyne.io.md`

### 7. Logseq Properties
- `journal-day:: [[YYYY-MM-DD]]`
- `source:: [[domain]]`

## Usage

```bash
cd ~/Nextcloud/scripts/logseq-processor
uv run logseq-processor
```

Options:
- `--model MODEL` - LLM model (default: qwen3.5:9b)
- `--force` - Re-process finished files
- `--debug` - Enable debug logging

## Files

```
logseq-processor/
├── pyproject.toml
├── config.yaml
├── README.md
├── uv.lock
├── .venv/
└── src/logseq_processor/
    ├── __init__.py
    ├── common.py       # Config, logging, rate limiter, warmup
    ├── utils.py        # URL normalization, path helpers
    ├── metadata.py     # Logseq format, journal-day, source
    ├── llm.py         # LLM calls
    ├── html_parser.py  # Web scraping with rate limiting
    ├── youtube.py      # YouTube transcripts
    ├── processor.py    # Article processing
    └── main.py        # File routing, queue, console
```

## Issues Fixed

1. **Cross-filesystem moves** - Use `shutil.move` instead of `Path.rename`
2. **Nextcloud file detection** - Added `on_moved` handler for sync behavior
3. **File size check** - Verify file is fully written before processing
4. **LLM timeouts** - Increased to 120s, reduced content to 8000 chars
5. **Short content** - Only errors on content < 10 chars

## Problems Encountered

1. **Ollama timeouts** - 30s not enough, increased to 120s
2. **Trafilatura extraction** - Some sites return empty content
3. **Filename formatting** - Domain + title format

## Console Output Format

```
[HH:MM:SS] 📁 Starting Logseq Processor
[HH:MM:SS] ⚙️  Model: qwen3.5:9b | Folder: ~/Nextcloud/Notes
[HH:MM:SS] ✓ Config loaded
[HH:MM:SS] ✓ Folders created
[HH:MM:SS] 🔥 Warming up LLM (qwen3.5:9b)...
[HH:MM:SS] ✓ LLM ready
[HH:MM:SS] 📋 Scanning folder...
[HH:MM:SS] Found: 12 .md, 0 .html, 0 tabs*.html, 0 other files
[HH:MM:SS] Processing: Fyne.io.md (fyne.io)
[ 1/47] Fetching: title... (domain)
[ 1/47] ✓ title (35.0s)
[HH:MM:SS] Moved: file.md → originals/file.md
```

## Next Steps / TODOs

1. Test watch mode with new files
2. Handle YouTube video transcripts properly
3. Add support for PDF processing
4. Improve error handling for specific HTTP errors
