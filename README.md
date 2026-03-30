# Logseq Processor

[![Tests](https://github.com/YOUR_USERNAME/logseq-processor/actions/workflows/test.yml/badge.svg)](https://github.com/YOUR_USERNAME/logseq-processor/actions/workflows/test.yml)

**Complete article processing solution with GitHub Actions integration + hybrid Nextcloud sync.**

Automatically download articles from URLs, extract content, generate metadata with LLM, and create Logseq-ready markdown files. Choose between automatic Nextcloud integration (Way 1) or manual GitHub Actions UI (Way 2).

## ✨ Features

### Core Processing
- 🔗 **URL Processing**: Download, extract, normalize URLs with intelligent redirect following
- 🤖 **LLM Metadata**: Auto-generate titles, tags, and summaries using Ollama
- 📺 **YouTube Support**: Extract transcripts directly from YouTube videos
- 📊 **Batch Processing**: Process 100+ articles at once
- 🔄 **Rate Limiting**: Per-domain and global rate limiting to be respectful
- 📝 **Error Handling**: Dedicated folders for errors with detailed logging
- 🏷️ **Tab Support**: Extract multiple links from browser tab exports

### GitHub Actions
- ☁️ **Serverless Processing**: No local Ollama needed - GitHub provides Docker container
- 🚀 **End-to-End**: From URL submission to final markdown in one workflow
- ✅ **CI/CD Testing**: Automatic validation on push/PR
- 🔀 **Dual Workflows**: Queue-only or full processing options

### Hybrid Sync (Phase 6)
- 📁 **Way 1: Automatic Nextcloud Sync**
  - Drop files in `~/Nextcloud/Notes/`
  - Auto-detect, extract URLs, trigger GitHub
  - Results auto-sync back
  - Zero manual steps after setup!

- 🎯 **Way 2: Manual GitHub UI**
  - Paste URL in GitHub Actions
  - Click "Run workflow"
  - Results auto-sync back
  - Works from anywhere (phone, web)

## 🚀 Quick Start

### Way 1: Automatic Nextcloud Sync (Recommended)

**One-time setup:**

```bash
# 1. Install dependencies
uv sync

# 2. Get GitHub token: https://github.com/settings/tokens
#    (Select: Personal access tokens → Fine-grained)
#    (Permissions: contents:read+write, actions:read)
#    (Repository: your logseq-processor repo)

# 3. Set environment variable
export GITHUB_TOKEN=ghp_XXXXXXXXXXXXXXXXXXXX

# 4. Create Nextcloud articles folder (if needed)
mkdir -p ~/Nextcloud/Notes/articles
```

**Start the sync (two terminals):**

```bash
# Terminal 1: Watch for new files
python scripts/sync_nextcloud_to_github.py --watch

# Terminal 2: Pull results periodically
python scripts/pull_processed_articles.py --daemon
```

**Use it:**

```bash
# Create file with URL
echo "Check this out: https://github.blog/2024-latest" > ~/Nextcloud/Notes/news.md

# Wait ~10 minutes...

# Check results
ls ~/Nextcloud/Notes/articles/
# → news-latest-20260330.md (ready to use!)
```

**Monitor progress:**

```bash
tail -f ~/.logseq-processor/sync.log
```

### Way 2: Manual GitHub UI

1. Go to: **GitHub → Actions → "Process Articles (End-to-End)"**
2. Click **"Run workflow"** button
3. Fill in:
   - **URLs**: Comma-separated (e.g., `https://github.blog,https://example.com`)
   - **Titles**: (optional) Comma-separated titles
   - **Tags**: (optional) Common tags for all URLs
   - **Model**: (optional) Select Ollama model
4. Click **"Run workflow"**
5. Wait ~10 minutes for processing
6. Pull results: `git pull`
7. Use in Logseq: `~/Nextcloud/Notes/articles/`

## 📊 How It Works

### Way 1: Automatic Nextcloud Sync

```
You save file
    ↓
sync_nextcloud_to_github.py detects (2-5 sec)
    ↓
Extracts URL from file content
    ↓
HTTP POST to GitHub API
    ├─→ GitHub Actions triggered
    │   ├─ Setup Python
    │   ├─ Start Docker Ollama
    │   ├─ Download article HTML
    │   ├─ Extract readable content
    │   ├─ Send to Ollama LLM
    │   ├─ Generate: title, tags, summary
    │   ├─ Create markdown file
    │   └─ git commit + push
    │
pull_processed_articles.py checks (every 5 min)
    ↓
git pull ← Results synced
    ↓
cp articles/ to Nextcloud
    ↓
Ready to use in Logseq!
```

### Way 2: Manual GitHub UI

```
You input URL → GitHub Actions → Same pipeline → git pull → Use in Logseq
```

## 📁 Project Structure

```
logseq-processor/
├── .github/workflows/
│   ├── process-articles.yml              # Main end-to-end workflow (Way 2 UI)
│   ├── process-articles-queue-only.yml   # Alternative: queue-only
│   ├── test.yml                          # CI/CD validation
│   └── sync-processed.yml                # Result synchronization
│
├── scripts/
│   ├── sync_nextcloud_to_github.py       # Way 1: File watcher + API trigger
│   ├── pull_processed_articles.py        # Way 1: Pull daemon + sync
│   ├── validate_urls.py                  # URL validation helper
│   ├── queue_to_markdown.py              # Queue file generator
│   └── check_queue.py                    # Queue status monitor
│
├── src/
│   ├── main.py                           # Local processor (optional)
│   ├── processor.py                      # Article processing logic
│   ├── llm.py                            # Ollama integration
│   ├── html_parser.py                    # Content extraction
│   ├── youtube.py                        # YouTube transcript support
│   └── ...other modules...
│
├── docs/
│   ├── SYNC_SETUP.md                     # Way 1 complete setup guide
│   ├── GITHUB_ACTIONS.md                 # Full architecture documentation
│   └── IMPLEMENTATION_SUMMARY.md         # Technical reference
│
├── queue/                                # Queue tracking
│   ├── status.json                       # Processing status
│   └── .gitkeep
│
├── config.yaml                           # Configuration (edit to customize)
├── pyproject.toml                        # Python dependencies
└── README.md                             # This file
```

## ⚙️ Configuration

Edit `config.yaml` to customize:

```yaml
# Article processor settings
model: qwen3.5:9b                    # LLM model
default_delay_seconds: 2             # Default delay between requests
max_retries: 3                       # Retry count for failed requests

# Folder to watch for input files
watch_folder: ~/Nextcloud/Notes

# Rate limiting
rate_limit:
  delay_per_domain: 2               # Delay between requests to same domain
  delay_global: 1                   # Global delay between all requests

# Sync configuration (Phase 6)
sync:
  enabled: true                      # Enable automatic Nextcloud sync
  nextcloud_folder: ~/Nextcloud/Notes
  github_workflow_id: process-articles
  pull_interval_seconds: 300         # Check for results every 5 min

# LLM settings
llm:
  max_parallel_jobs: 1               # Concurrent LLM jobs (increase for speed)
  timeout_seconds: 120               # Timeout per article
  temperature_attempts:
    - 0.05                          # Temperature progression on retries
    - 0.25
    - 0.50

# Output folders (relative to watch_folder)
folders:
  articles: articles
  processed: processed
  originals: originals
  errors: errors
  other: Other
```

## 🔧 Usage Modes

### Local Processing (Optional)

If you prefer local processing with your own Ollama:

```bash
# Watch folder and process with default worker (ingest + LLM)
uv run logseq-processor ~/Nextcloud/Notes

# Ingest only (extract content, queue for LLM)
uv run logseq-processor ~/Nextcloud/Notes --worker ingest

# LLM only (process queued articles)
uv run logseq-processor ~/Nextcloud/Notes --worker llm

# Specific model and force reprocessing
uv run logseq-processor ~/Nextcloud/Notes --model mistral:7b --force
```

### Parallel Processing

Configure concurrent LLM jobs:

```yaml
llm:
  max_parallel_jobs: 2  # Or higher on powerful machines
```

## 📚 Documentation

### For Setup & Deployment
- **[docs/SYNC_SETUP.md](docs/SYNC_SETUP.md)** - Complete Way 1 setup guide with troubleshooting
  - GitHub token creation
  - Running both scripts
  - 7 common issues with solutions
  - Performance tuning
  - Background service setup

### For Architecture & Details
- **[docs/GITHUB_ACTIONS.md](docs/GITHUB_ACTIONS.md)** - Full technical documentation
  - Complete workflow breakdown
  - Docker Ollama integration
  - Step-by-step execution flow
  - Advanced configuration

### For Reference
- **[docs/IMPLEMENTATION_SUMMARY.md](docs/IMPLEMENTATION_SUMMARY.md)** - Technical reference

## 🔄 Workflow Comparison

| Feature | Way 1 (Auto) | Way 2 (Manual) | Local |
|---------|--------------|----------------|-------|
| **Setup Complexity** | Medium | Low | Medium |
| **Auto-Detection** | ✅ Watchdog | ✗ Manual | ✅ Watchdog |
| **Nextcloud Native** | ✅ Natural | ✅ Via git pull | ✅ Native |
| **Batch Processing** | ✅ All at once | ✅ Comma-separated | ✅ All at once |
| **Works Offline** | ✗ Needs GitHub | ✗ Needs GitHub | ✅ Yes |
| **Requires Daemon** | ✅ 2 scripts | ✗ None | ✗ None |
| **Works from Phone** | ✗ | ✅ GitHub UI | ✗ |
| **Processing Speed** | ~10 min/article | ~10 min/article | ~10 min/article |
| **Ollama Needed** | ✗ GitHub has it | ✗ GitHub has it | ✅ Local |

## 🔐 Authentication

### Way 1 & 2: GitHub Token

Get a token at: https://github.com/settings/tokens

**Create fine-grained personal access token:**
1. Token name: `logseq-processor-sync`
2. Expiration: 90 days (or longer)
3. Resource owner: Your username
4. Repository access: Only `logseq-processor`
5. Permissions:
   - `Contents`: Read and write
   - `Actions`: Read and write

**Set environment variable:**

```bash
export GITHUB_TOKEN=ghp_XXXXXXXXXXXXXXXXXXXX

# Make permanent (add to ~/.bashrc or ~/.zshrc)
echo 'export GITHUB_TOKEN=ghp_XXXXXXXXXXXXXXXXXXXX' >> ~/.zshrc
source ~/.zshrc
```

## 🐛 Troubleshooting

### Common Issues

**"GITHUB_TOKEN not set"**
```bash
export GITHUB_TOKEN=ghp_XXXXXXXXXXXXXXXXXXXX
echo $GITHUB_TOKEN  # Verify it's set
```

**"Workflow not found"**
- Check workflow file exists: `.github/workflows/process-articles.yml`
- Verify repo name matches in scripts
- Ensure GitHub Actions is enabled in repo settings

**"Permission denied"**
- Token may be expired (regenerate at GitHub settings)
- Check token has correct permissions (contents:read+write, actions:read)

**"Files not syncing back"**
- Verify pull script is running: `ps aux | grep pull_processed`
- Test git manually: `git pull origin main`
- Check articles folder exists: `mkdir -p ~/Nextcloud/Notes/articles`

**"Slow processing"**
- First run downloads Ollama model (~5GB) - takes 2-5 minutes
- Subsequent runs use cached model
- Very long articles (>50KB) take 20-30 minutes

For more issues, see **[docs/SYNC_SETUP.md](docs/SYNC_SETUP.md#troubleshooting)**.

## 📊 Performance

### Processing Time Per Article

- **Setup & Python**: 1-2 min (first run only)
- **Model Download**: 2-5 min (first run only, then cached)
- **Content Extraction**: 2-5 min
- **LLM Processing**: 5-15 min ⏱️ (slowest part)
- **Commit & Push**: 30 sec
- **Total**: ~10-30 min (average 15 min)

### Optimization Tips

1. **Batch processing** - Process 10 URLs at once (faster than 10 individual runs)
2. **Reuse model cache** - Second article is faster (model already loaded)
3. **Increase timeout** - For very long articles:
   ```yaml
   llm:
     timeout_seconds: 240  # Increase from 120
   ```
4. **Reduce pull interval** - Check for results more frequently:
   ```yaml
   sync:
     pull_interval_seconds: 60  # Instead of 300 (5 min)
   ```

## 🔗 Link Resolution

The processor intelligently resolves URLs:

- Follows HTTP redirects with `HEAD` requests
- Falls back to `GET` if `HEAD` fails
- Extracts wrapped URLs from tracking parameters
- Looks for canonical URLs in HTML metadata
- Detects and rejects unsafe/local targets (localhost, private IPs)
- Deduplicates by resolved canonical URL

## ⚠️ Error Handling

Files that fail processing are moved to the `errors/` folder with detailed suffixes:

- `_error_empty_content_` - No readable content extracted
- `_error_no_url_found_` - URL couldn't be parsed from file
- `_error_http_blocked_` - Server returned 403/429
- `_error_parse_error_` - HTML parsing failed
- `_error_timeout_` - LLM processing timed out

Check error logs for details: `~/.logseq-processor/logs/processor.log`

## 📦 Dependencies

- **Python**: 3.11+
- **uv**: Python package manager (for installation)
- **watchdog**: File system monitoring (Way 1)
- **requests**: HTTP client
- **beautifulsoup4**: HTML parsing
- **pyyaml**: Configuration
- **trafilatura**: Content extraction
- **ollama**: LLM client
- **youtube-transcript-api**: YouTube support

Install all with: `uv sync`

## 🎯 Project Status

- ✅ Phase 1: Queue System (complete)
- ✅ Phase 2: GitHub Actions Workflows (complete)
- ✅ Phase 3: Documentation (complete)
- ✅ Phase 4: Best Practices (complete)
- ✅ Phase 5: Docker Ollama + LLM (complete)
- ✅ Phase 6: Hybrid Nextcloud Sync (complete)

**Overall Status**: Production-ready ✓

## 📝 License

MIT License - See LICENSE file

## 🤝 Contributing

Found a bug or have a suggestion? Open an issue or submit a pull request!

---

## 🚀 Getting Started

**Choose your path:**

1. **Want automatic Nextcloud sync?**
   - Follow: [docs/SYNC_SETUP.md](docs/SYNC_SETUP.md)
   - Command: `python scripts/sync_nextcloud_to_github.py --watch`

2. **Want simple GitHub UI?**
   - Go to: GitHub → Actions → "Process Articles (End-to-End)"
   - Input URL → Run workflow

3. **Want technical details?**
   - Read: [docs/GITHUB_ACTIONS.md](docs/GITHUB_ACTIONS.md)

4. **Need troubleshooting help?**
   - Check: [docs/SYNC_SETUP.md#troubleshooting](docs/SYNC_SETUP.md#troubleshooting)

---

**Questions?** Check the docs or open an issue!

Happy processing! 🚀
