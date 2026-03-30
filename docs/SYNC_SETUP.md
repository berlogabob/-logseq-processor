# Hybrid Nextcloud ↔ GitHub Actions Sync Setup

This guide shows how to set up automatic synchronization between your Nextcloud Notes folder and GitHub Actions for article processing.

## Overview

You have **two ways** to process articles:

### Way 1: Automatic Nextcloud Sync (Recommended)
- Drop `.md` files in `~/Nextcloud/Notes/`
- Sync script detects them
- Automatically sends to GitHub Actions
- GitHub processes article
- Pull script syncs results back
- No manual steps!

### Way 2: Manual GitHub UI
- Go to GitHub Actions website
- Paste URL manually
- GitHub processes
- Results auto-sync back
- Best for quick processing of single articles

Both ways work in parallel and can be used together.

---

## Prerequisites

### 1. GitHub Token

You need a GitHub Personal Access Token to authenticate API calls.

**Get your token:**

1. Go to: https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new fine-grained personal access token"
3. Fill in:
   - **Token name**: `logseq-processor-sync`
   - **Expiration**: 90 days (or longer)
   - **Resource owner**: Your username
   - **Repository access**: `Only select repositories` → Select `logseq-processor`
   - **Permissions**:
     - `Contents`: Read and write
     - `Actions`: Read
4. Click "Generate token"
5. **Copy the token** (you won't see it again!)

### 2. Set Environment Variable

Add your token to your shell profile so it's available when you run the scripts:

```bash
# Add to ~/.bashrc, ~/.zshrc, or ~/.bash_profile
export GITHUB_TOKEN=ghp_XXXXXXXXXXXXXXXXXXXX
```

Then reload your shell:

```bash
source ~/.zshrc  # or ~/.bashrc
```

**Verify it's set:**

```bash
echo $GITHUB_TOKEN
```

Should output your token (at least the first 20 chars).

### 3. Python Dependencies

The scripts require `watchdog` for file system monitoring.

```bash
cd ~/Nextcloud/scripts/logseq-processor
uv sync
```

This installs all required packages including `watchdog`, `requests`, `pyyaml`, and `beautifulsoup4`.

---

## Way 1: Automatic Nextcloud Sync

### Setup (One-time)

1. **Verify GitHub token is set:**
   ```bash
   echo $GITHUB_TOKEN
   ```

2. **Check Nextcloud folder exists:**
   ```bash
   ls -la ~/Nextcloud/Notes/
   ```
   Should see your `articles/` subfolder or create it:
   ```bash
   mkdir -p ~/Nextcloud/Notes/articles
   ```

3. **Test the connection** (optional but recommended):
   ```bash
   cd ~/Nextcloud/scripts/logseq-processor
   python scripts/sync_nextcloud_to_github.py --check
   ```
   Should show empty tracker: `{"synced_files": [], "last_sync": null}`

### Running Way 1 (Two Scripts)

Open **two terminal windows** or tabs:

**Terminal 1 - Sync Watcher (uploads to GitHub):**

```bash
cd ~/Nextcloud/scripts/logseq-processor
python scripts/sync_nextcloud_to_github.py --watch
```

You should see:
```
[15:30:00] INFO: Starting sync watcher on: /Users/you/Nextcloud/Notes
[15:30:00] INFO: Watching for .md and tabs*.html files...
[15:30:00] INFO: Press Ctrl+C to stop
```

**Terminal 2 - Pull Daemon (downloads from GitHub):**

```bash
cd ~/Nextcloud/scripts/logseq-processor
python scripts/pull_processed_articles.py --daemon
```

You should see:
```
[15:30:05] INFO: Starting pull sync daemon (interval: 300s)
[15:30:05] INFO: Press Ctrl+C to stop
```

Both scripts will now run continuously in the background, watching and syncing.

### Using Way 1

Once both scripts are running, here's how to process articles:

**Example 1: Single article from markdown**

1. Create file: `~/Nextcloud/Notes/github-news.md`

2. Add content:
   ```
   Interesting article about GitHub features:
   https://github.blog/2024-new-copilot-updates/
   ```

3. Save the file

4. **Wait for results:**
   - Sync script detects file (2-5 sec)
   - Extracts URL
   - Calls GitHub API
   - GitHub Actions processes (8-15 min)
   - Pull script syncs back (every 5 min)

5. Check results:
   ```bash
   ls ~/Nextcloud/Notes/articles/
   ```
   Should see: `github-new-copilot-updates-20260330.md`

**Example 2: Multiple articles from browser tabs**

1. Export tabs from your browser as HTML:
   - Chrome: Right-click tab bar → "Save all tabs to a file"
   - Firefox: Use extension like "Tab Save"
   - Safari: Copy all tabs (hold shift, right-click)

2. Save HTML file to: `~/Nextcloud/Notes/tabs_20260330.html`

3. Sync script automatically:
   - Detects tabs file
   - Extracts all links
   - Triggers workflow with all URLs
   - GitHub processes all articles in parallel
   - Pull script syncs all results

4. Check results:
   ```bash
   ls ~/Nextcloud/Notes/articles/ | grep "20260330"
   ```
   Should show multiple articles from that batch.

### Monitoring Way 1

**Check what files have been synced:**

```bash
python scripts/sync_nextcloud_to_github.py --check
```

Output example:
```json
{
  "synced_files": [
    {
      "name": "github-news.md",
      "urls": ["https://github.blog/2024-new-copilot-updates/"],
      "triggered_at": "2026-03-30T15:30:05Z",
      "workflow_id": 1234567890,
      "status": "queued"
    }
  ],
  "last_sync": "2026-03-30T15:30:05Z",
  "stats": {
    "total_synced": 1,
    "total_done": 0,
    "total_errors": 0
  }
}
```

**View sync logs:**

```bash
tail -f ~/.logseq-processor/sync.log
```

Real-time log output:
```
[15:30:02] INFO: Processing: github-news.md
[15:30:03] INFO: ✓ Workflow triggered: https://github.blog/2024-new-copilot-updates/
[15:30:04] INFO: ✓ Synced github-news.md (1 URL(s))
[15:35:00] INFO: Running git fetch...
[15:35:02] INFO: ✓ git pull successful
[15:35:03] INFO: ✓ Synced: github-new-copilot-updates-20260330.md → articles/
```

---

## Way 2: Manual GitHub UI

This method is already available! You don't need to start any scripts.

### Using Way 2

1. Go to: https://github.com/your-username/logseq-processor
2. Click: **Actions** tab
3. Click: **"Process Articles (End-to-End)"** workflow
4. Click: **"Run workflow"** button
5. Fill in the form:
   - **URLs:** `https://github.blog/article1,https://example.com/article2`
   - **Titles:** (optional) `Title 1,Title 2`
   - **Tags:** (optional) `github,ai,example`
   - **Ollama Model:** (optional) Select from dropdown
6. Click: **"Run workflow"** button

### Monitoring Way 2

1. Watch workflow run in real-time:
   - GitHub Actions shows progress
   - Click job to see logs

2. Pull results when done:
   ```bash
   cd ~/Nextcloud/scripts/logseq-processor
   git pull origin main
   ```

3. Results appear in:
   ```bash
   ls ~/Nextcloud/Notes/articles/
   ```

---

## Troubleshooting

### Issue 1: "GITHUB_TOKEN not set"

**Error:** `GitHub token environment variable not set`

**Solution:**

```bash
export GITHUB_TOKEN=ghp_XXXXXXXXXXXXXXXXXXXX
```

Verify it's set:

```bash
echo $GITHUB_TOKEN
```

**Make it permanent:**

Add to `~/.zshrc` or `~/.bashrc`:

```bash
echo 'export GITHUB_TOKEN=ghp_XXXXXXXXXXXXXXXXXXXX' >> ~/.zshrc
source ~/.zshrc
```

### Issue 2: "Workflow not found"

**Error:** `HTTP 404: Workflow not found`

**Possible causes:**

1. Workflow file name is wrong
2. Repository name is wrong

**Solution:**

Check:
- Workflow file exists: `.github/workflows/process-articles.yml`
- Repository name in `git remote -v` matches what you put in code

Verify:

```bash
git remote -v
# Should show: origin  https://github.com/YOUR-USERNAME/logseq-processor.git
```

### Issue 3: "Permission denied"

**Error:** `HTTP 403: Permission denied` or `HTTP 401: Unauthorized`

**Solution:**

1. Check token is valid:
   ```bash
   curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
   ```
   Should show your user info, not an error.

2. Regenerate token if expired:
   - Go to: https://github.com/settings/tokens
   - Click on your token
   - Click "Regenerate token"
   - Copy new token
   - Update `GITHUB_TOKEN` environment variable

### Issue 4: "Files not syncing back"

**Error:** You don't see processed articles in Nextcloud after GitHub Actions completes

**Possible causes:**

1. Pull script not running
2. Git is not authenticated
3. Articles folder doesn't exist

**Solution:**

1. Check pull script is running:
   ```bash
   ps aux | grep pull_processed_articles
   ```

2. Check git can pull:
   ```bash
   cd ~/Nextcloud/scripts/logseq-processor
   git pull origin main
   # Should succeed without password prompt (using SSH or saved credentials)
   ```

3. Create articles folder if missing:
   ```bash
   mkdir -p ~/Nextcloud/Notes/articles
   ```

4. Run pull manually:
   ```bash
   python scripts/pull_processed_articles.py --once
   ```

### Issue 5: "Watched files are being reprocessed"

**Error:** Same file gets processed multiple times

**Solution:**

The sync script tracks which files have been synced in `~/.logseq-processor/sync_tracker.json`. Files shouldn't be reprocessed unless you manually delete this file.

If files are being reprocessed:

1. Check tracker:
   ```bash
   python scripts/sync_nextcloud_to_github.py --check
   ```

2. If tracker is corrupted, delete it:
   ```bash
   rm ~/.logseq-processor/sync_tracker.json
   ```
   It will be recreated fresh on next file.

### Issue 6: "Slow processing"

**Error:** Articles are taking very long to process (>30 min)

**Possible causes:**

1. Long articles (> 50KB)
2. Ollama model is overloaded
3. GitHub Actions is slow (less common)

**Solution:**

This is expected for:
- Very long articles: Can take 20-30 minutes
- Multiple parallel articles: GitHub processes sequentially with max_parallel_jobs=1

Options:

1. **Wait** - Processing will eventually complete
2. **Check logs** - GitHub Actions shows progress:
   - Go to: Actions → Workflow run → View logs
3. **Increase timeout** - If article is long and timing out:
   - Update `llm.timeout_seconds` in `config.yaml`
   - Default is 120 seconds, can increase to 180 or 240

### Issue 7: "Ollama model not found"

**Error:** `Failed to pull model: model not found`

**Possible causes:**

1. Model name is wrong (typo)
2. Internet connection is slow
3. GitHub Actions timeout

**Solution:**

1. Check model name in config:
   ```bash
   grep "model:" config.yaml
   ```

2. Verify it's a valid Ollama model:
   - Visit: https://ollama.ai/library
   - Search for your model
   - Make sure spelling matches exactly

3. For large models (>7GB), first run will be slow:
   - Expect 5-10 min for download
   - Subsequent runs will be fast (model cached)

---

## Running as Background Services (Advanced)

Instead of keeping terminals open, you can run scripts as background services.

### macOS (using launchd)

Create `~/Library/LaunchAgents/com.logseq.sync.watch.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.logseq.sync.watch</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/YOU/Nextcloud/scripts/logseq-processor/scripts/sync_nextcloud_to_github.py</string>
        <string>--watch</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/logseq-sync-watch.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/logseq-sync-watch-error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>GITHUB_TOKEN</key>
        <string>ghp_XXXXXXXXXXXXXXXXXXXX</string>
    </dict>
</dict>
</plist>
```

Then load it:

```bash
launchctl load ~/Library/LaunchAgents/com.logseq.sync.watch.plist
```

Check status:

```bash
launchctl list | grep logseq
```

Stop it:

```bash
launchctl unload ~/Library/LaunchAgents/com.logseq.sync.watch.plist
```

### Linux (using systemd)

Create `~/.config/systemd/user/logseq-sync.service`:

```ini
[Unit]
Description=Logseq Processor Sync
After=network.target

[Service]
Type=simple
Environment="GITHUB_TOKEN=ghp_XXXXXXXXXXXXXXXXXXXX"
ExecStart=/usr/bin/python3 /home/you/Nextcloud/scripts/logseq-processor/scripts/sync_nextcloud_to_github.py --watch
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

Then:

```bash
systemctl --user start logseq-sync
systemctl --user enable logseq-sync
systemctl --user status logseq-sync
```

---

## Performance Tips

### 1. Reduce pull interval to sync faster

Edit `config.yaml`:

```yaml
sync:
  pull_interval_seconds: 60  # Check every 1 minute instead of 5
```

Trade-off: More frequent API calls to GitHub, uses more bandwidth.

### 2. Batch processing

Instead of dropping single `.md` files one at a time, use `tabs*.html` to batch multiple URLs:

- Export 10 browser tabs to HTML
- Drop HTML file
- All 10 URLs process together
- Single GitHub workflow run for all

Benefit: Saves workflow runs, faster overall processing.

### 3. Monitor with logs

Always check logs when something seems slow:

```bash
tail -f ~/.logseq-processor/sync.log
```

Watch for:
- URL extraction timing
- GitHub API response times
- Git pull timing

### 4. Increase LLM timeout for long articles

Edit `config.yaml`:

```yaml
llm:
  timeout_seconds: 180  # Increase from 120
```

Helps with very long articles that take 2+ min to process.

---

## Configuration Reference

All settings in `config.yaml` `sync` section:

```yaml
sync:
  # Enable/disable automatic sync
  enabled: true
  
  # Folder to watch for input files
  nextcloud_folder: ~/Nextcloud/Notes
  
  # GitHub Actions workflow name (usually "process-articles")
  github_workflow_id: process-articles
  
  # How often to check for new articles (in seconds)
  # Default: 300 (5 minutes)
  pull_interval_seconds: 300
  
  # Where sync tracker stores data
  sync_cache_file: ~/.logseq-processor/sync_tracker.json
```

---

## Next Steps

1. **[Set up GitHub token](#github-token)** (if not done)
2. **Start Way 1:**
   ```bash
   # Terminal 1
   python scripts/sync_nextcloud_to_github.py --watch
   
   # Terminal 2
   python scripts/pull_processed_articles.py --daemon
   ```
3. **Drop a test file:**
   ```bash
   echo "Check this: https://github.blog/test" > ~/Nextcloud/Notes/test.md
   ```
4. **Monitor the flow:**
   ```bash
   tail -f ~/.logseq-processor/sync.log
   ```
5. **Wait for results** (~10 min)
6. **Check your Nextcloud:**
   ```bash
   ls ~/Nextcloud/Notes/articles/
   ```

You should see a new processed article!

---

## Getting Help

**Check logs:**

```bash
tail -20 ~/.logseq-processor/sync.log
```

**Verify setup:**

```bash
# Token set?
echo $GITHUB_TOKEN

# Repo ok?
git -C ~/Nextcloud/scripts/logseq-processor remote -v

# Nextcloud folder exists?
ls -la ~/Nextcloud/Notes/

# GitHub API accessible?
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
```

**Contact:**

Open an issue on GitHub with:
1. Full error message
2. Output of `python scripts/sync_nextcloud_to_github.py --check`
3. Last 20 lines of sync.log
4. Your OS and Python version
