# Copilot Instructions for `logseq-processor`

## Build, test, and lint commands

- Install dependencies: `uv sync`
- Run the CLI locally: `uv run logseq-processor [path] [--model MODEL] [--force] [--debug]`
- Alternative module entrypoint: `uv run python -m src.main [path] [--model MODEL] [--force] [--debug]`

There are currently no dedicated test or lint commands configured in `pyproject.toml` and no `tests/` directory.

Single-test command: not available yet (no test suite present).

## High-level architecture

- Entry point is `src/main.py` (`logseq-processor` console script in `pyproject.toml`).
- Runtime has two phases:
  - Initial batch scan (`scan_folder`) of the watch folder.
  - Continuous watch mode via `watchdog` (`watch_folder` + `WatchHandler`).
- Runtime now supports worker split via `--worker all|ingest|llm`:
  - `ingest`: file watching/parsing, short-link expansion, fetch/extract, queueing.
  - `llm`: summarization/final markdown generation from queued artifacts.
- Files are classified and routed by type:
  - `tabs*.html` -> parsed as multi-link queue (`parse_tabs_html`), then each URL processed.
  - short `.md` files (<=2 non-empty lines) -> URL extracted and processed.
  - plain `.html` -> moved to `originals`.
  - unsupported extensions -> moved to `Other`.
- URL processing pipeline (`process_article` in `src/processor.py`):
  - Validate + normalize URL and skip already-processed URLs via in-memory cache seeded from existing article markdown (`url:: ...`).
  - Content extraction:
    - YouTube URLs use `youtube_transcript_api` (`src/youtube.py`).
    - Other URLs use `trafilatura` first, then `requests` fallback (`src/html_parser.py`).
  - Metadata extraction via Ollama chat JSON response (`src/llm.py`) into `ArticleMetadata` (`src/metadata.py`), with retries and temperature progression from config.
  - Final Logseq markdown emitted via `build_content` with frontmatter-like `key:: value` properties.
- Global cross-cutting services in `src/common.py`:
  - Singleton `Config` loaded from repository `config.yaml`.
  - Global/per-domain rate limiter.
  - Logging with timed rotation (`~/.logseq-processor/logs/processor.log`).
- Queue persistence for tab batches is stored at `~/.logseq-processor/queue.json` (`QueueManager`), allowing resume on restart.
- Pipeline queue persists in `~/.logseq-processor/pipeline.db` (`PipelineQueue`) for staged ingest/LLM processing.

## Key repository conventions

- Treat `config.yaml` in repo root as runtime source of truth; code reads it through `Config.get()` singleton.
- Preserve Logseq property format exactly (`title::`, `tags::`, `journal-day::`, `url::`, etc.); downstream duplicate detection depends on `url::` lines in generated `.md` files.
- Keep URL normalization behavior stable (`normalize_url`): strips `www.`/`m.`, drops fragments, and retains only selected query keys (`v`, `p`, `id`, `q`, `search`).
- Maintain folder routing semantics from config (`articles`, `processed`, `originals`, `errors`, `Other`) and avoid processing files already inside those buckets.
- Errors are represented via `ProcessingError` enum and often encoded into filename suffixes when moving to `errors` (via `get_error_suffix`).
- For LLM metadata extraction, expected response contract is strict JSON matching `ArticleMetadata`; code uses cleanup + pydantic validation and fallback metadata.
- User-facing operational logs are printed with timestamped `log_print(...)`; structured logs go through module logger configured in `common.py`.
- Watch-mode file handling uses debounce and skip patterns (`.tmp`, `.sync-conflict`, `~`, `.part`, `.crdownload`, `.icloud`); preserve these checks when modifying ingestion behavior.
