# Logseq Processor

Logseq article processor with tabs support, URL normalization, and rate limiting.

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
# Full legacy behavior (fetch + summarize in one flow)
uv run logseq-processor [path] --worker all

# Ingestion only (watch files, parse links, expand short URLs, fetch/extract, queue LLM jobs)
uv run logseq-processor [path] --worker ingest

# LLM only (consume queued jobs and produce final Logseq notes)
uv run logseq-processor [path] --worker llm
```

## Configuration

Edit `config.yaml` to customize settings.
