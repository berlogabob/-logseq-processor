# Logseq Processor

Process articles with AI-powered metadata extraction for Logseq.

## 🎯 How It Works

**Two ways to process articles:**

### Option 1: Local Processing (Recommended) ⭐

1. **Add files to inbox** → Place `.md` files in `01_inbox/`
2. **Run processor locally** → `uv run logseq-processor 01_inbox/`
3. **Check results** → Processed files appear in your configured output folder

**Requires:** Python 3.11+, Ollama running locally

### Option 2: Queue URLs via GitHub Actions

1. **Queue URLs** → Use GitHub Actions "Queue URLs for Processing" workflow
2. **Process locally** → Run `uv run logseq-processor` to process queued items
3. **Sync results** → Use "Sync Processed Files" workflow to push results back

## 📁 Folder Structure

```
01_inbox/        ← Place .md files or short-link files here
02_processing/   ← Files currently being processed
03_success/      ← ✓ Successfully processed articles
04_failed/       ← ✗ Files with errors (check filename for reason)
originals/       ← Backup of original files
queue/           ← URL queue for batch processing
```

## 🚀 Quick Start (Local Processing)

### Step 1: Install Dependencies

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
cd logseq-processor
uv sync
```

### Step 2: Start Ollama

```bash
# Make sure Ollama is running with your model
ollama pull qwen3.5:9b  # or your preferred model
ollama serve
```

### Step 3: Add Files to Process

```bash
# Copy article files to the inbox folder
cp ~/Downloads/article.md 01_inbox/
# Or create short-link files with just a URL
echo "https://example.com/article" > 01_inbox/article.md
```

### Step 4: Run the Processor

```bash
# Process all files in inbox
uv run logseq-processor 01_inbox/

# Or run in watch mode (continuous monitoring)
uv run logseq-processor --watch

# Force reprocessing (bypass cache)
uv run logseq-processor 01_inbox/ --force

# Use different model
uv run logseq-processor 01_inbox/ --model llama3:8b

# Debug mode
uv run logseq-processor 01_inbox/ --debug
```

### Step 5: Use Results

Processed articles appear in the configured output folder (check `config.yaml`).
Successfully processed: `03_success/`
Failed files: `04_failed/` (with error in filename)

## ✅ What Gets Generated

**Input file:** `article.md`

**Success:** `03_success/article-Article-Title-20260330-153645.md`
```markdown
title:: Article Title
tags:: technology, ai
url:: https://original-url.com
summary:: Generated summary of the article...

Full article content here...
```

**Error:** `04_failed/article_ERROR_http_blocked_403.md`
- Shows the error reason in filename
- Original file included (for your reference)

## 🔧 Error Codes

| Error | Meaning | What to do |
|-------|---------|-----------|
| `ERROR_http_blocked_403` | Server rejected request | Wait, try different URL |
| `ERROR_http_blocked_429` | Rate limited | Try again later |
| `ERROR_empty_content` | No readable content | Check URL, try different source |
| `ERROR_parse_error` | HTML parsing failed | Check URL format |
| `ERROR_timeout_120s` | Processing took too long | Very long article? Try shorter one |
| `ERROR_url_invalid` | Invalid URL format | Check URL spelling |

## 🔄 Retrying Failed Files

If a file fails, you can retry it:

**Simple retry** (fixes the original issue):
```bash
# Fix the issue first (wait a minute, try different URL, etc)
mv 04_failed/article_ERROR_http_blocked_403.md 01_inbox/article.md
git add .
git commit -m "Retry: article.md"
git push
```

**Force retry** (ignores cache):
```bash
# Forces reprocessing even if seen before
mv 04_failed/article_ERROR_http_blocked_403.md 01_inbox/article--force.md
git add .
git commit -m "Force retry: article.md"
git push
```

## 🔄 Using GitHub Actions (Optional)

### Workflow 1: Queue URLs for Processing

Use this to manually queue URLs for later processing:

1. Go to **Actions** tab in GitHub
2. Select **"Queue URLs for Processing (Manual)"**
3. Click **"Run workflow"**
4. Enter URLs (comma-separated)
5. Optionally add titles, tags, force reprocessing
6. URLs are added to `queue/` folder

### Workflow 2: Sync Processed Files

After processing locally, sync results back to GitHub:

1. Go to **Actions** tab
2. Select **"Sync Processed Files"**
3. Click **"Run workflow"**
4. Processed articles are committed and pushed

### Workflow 3: Tests and Validation

Runs automatically on every push to validate code integrity.

## 📊 How Processing Works

1. **File detection**: Processor scans `01_inbox/` for files
2. **File classification**: 
   - Short `.md` files (≤2 lines) → Extract URL
   - `tabs*.html` → Parse as multi-link batch
   - Plain `.html` → Move to originals
3. **URL processing**:
   - Validate & normalize URL
   - Check if already processed (cache)
   - Fetch content (Trafilatura for web, YouTube API for videos)
4. **LLM metadata extraction**: Generate title, tags, summary, journal-day
5. **Create Logseq markdown**: Format with frontmatter-style properties
6. **Save result**: 
   - Success → Configured output folder
   - Error → `04_failed/` with error code in filename

## ⏱️ Processing Time

- **Local processing**: 10-30 seconds per article (with local Ollama)
- **First run**: May need to download model (~5GB for qwen3.5:9b)
- **Factors**: Content size, model speed, hardware (GPU recommended)

## 🐛 Troubleshooting

**Ollama connection errors?**
- Make sure Ollama is running: `ollama serve`
- Check if model is available: `ollama list`
- Verify Ollama URL in `config.yaml` (default: `http://localhost:11434`)

**Files not being processed?**
- Verify files are in `01_inbox/` folder
- Check if URLs are valid and accessible
- Look at `~/.logseq-processor/logs/processor.log` for errors

**"Already processed" skipping files?**
- Processor caches processed URLs to avoid duplicates
- Use `--force` flag to bypass cache
- Or delete the file from output folder and reprocess

**Processing is slow?**
- First run downloads Ollama model (~5GB)
- Large articles take longer to process
- GPU acceleration significantly speeds up LLM processing
- Adjust `llm.max_parallel_jobs` in `config.yaml` (default: 2)

## 📦 Dependencies

- Python 3.11+ (3.12 or 3.13 recommended)
- uv (Python package manager)
- Ollama (for LLM metadata extraction)
- Required Python packages (installed via `uv sync`):
  - trafilatura (web content extraction)
  - beautifulsoup4 (HTML parsing)
  - ollama (Ollama API client)
  - watchdog (file monitoring)
  - pydantic (data validation)
  - requests (HTTP client)
  - youtube_transcript_api (YouTube transcripts)
  - pyyaml (config file parsing)

## 🎯 Features

✅ **Automatic URL extraction** from markdown files  
✅ **LLM metadata generation** (title, tags, summary, journal-day)  
✅ **YouTube transcript support** (no scraping needed)  
✅ **Short-link expansion** (t.co, bit.ly, etc.)  
✅ **Multi-URL batch processing** (tabs*.html files)  
✅ **Duplicate detection** (URL-based caching)  
✅ **Rate limiting** (per-domain and global)  
✅ **Worker split mode** (separate ingest/LLM workers)  
✅ **Watch mode** (continuous folder monitoring)  
✅ **Error handling** with detailed error codes  
✅ **Logseq-ready** markdown output  
✅ **Configurable** via `config.yaml`

## 📝 Configuration

Edit `config.yaml` in the repository root to customize:

```yaml
# Watch folder
folders:
  watch: "01_inbox"
  
# LLM settings
llm:
  base_url: "http://localhost:11434"
  model: "qwen3.5:9b"
  max_parallel_jobs: 2  # Concurrent LLM requests
  
# Rate limiting
http:
  rate_limit_requests: 10
  rate_limit_period: 60
  
# And many more options...
```

See `config.yaml` for full configuration options.

## 🔧 Advanced Usage

### Worker Split Mode

Run separate workers for ingest and LLM processing:

```bash
# Terminal 1: Ingest worker (fetch/extract content)
uv run logseq-processor --worker ingest

# Terminal 2: LLM worker (generate metadata)
uv run logseq-processor --worker llm
```

### Queue Management

```bash
# Check queue status
python scripts/check_queue.py

# Validate URLs before queueing
python scripts/validate_urls.py "https://example.com" "https://another.com"

# Queue URLs to markdown
python scripts/queue_to_markdown.py "https://example.com" --tags="tech,ai"
```

---

## 📚 Documentation

- **Architecture**: See `docs/` folder for detailed documentation
- **Configuration**: Full options in `config.yaml`
- **Logs**: `~/.logseq-processor/logs/processor.log`
- **Queue**: `~/.logseq-processor/queue.json`
- **Pipeline DB**: `~/.logseq-processor/pipeline.db`

---

**Version**: 2.0 (Worker Split, Pipeline Queue)  
**Last Updated**: March 30, 2026
