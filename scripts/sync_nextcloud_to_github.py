#!/usr/bin/env python3
"""
Sync Nextcloud files to GitHub Actions via API.

Watches ~/Nextcloud/Notes/ for new .md and tabs*.html files,
extracts URLs, and triggers the GitHub Actions workflow.

Usage:
    python scripts/sync_nextcloud_to_github.py --watch
"""

import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
import yaml
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# Setup logging
log_file = Path.home() / ".logseq-processor" / "sync.log"
log_file.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Constants
SKIP_PATTERNS = {".tmp", ".sync-conflict", "~", ".part", ".crdownload", ".icloud"}
TRACKER_FILE = Path.home() / ".logseq-processor" / "sync_tracker.json"
DEBOUNCE_TIMEOUT = 3  # seconds


def load_config() -> dict:
    """Load config.yaml from project root."""
    config_path = Path(__file__).parent.parent / "config.yaml"
    if not config_path.exists():
        logger.error(f"config.yaml not found at {config_path}")
        sys.exit(1)
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_github_token() -> str:
    """Get GitHub token from environment variable."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.error("GITHUB_TOKEN environment variable not set")
        logger.error("Set it with: export GITHUB_TOKEN=ghp_XXXXXXXXXXXX")
        sys.exit(1)
    return token


def extract_url_from_text(text: str) -> Optional[str]:
    """Extract first URL from text."""
    urls = re.findall(r"https?://[^\s<>\"'\)]+", text)
    for url in urls:
        url = url.rstrip(".,;:!?")
        if len(url) > 10:
            return url
    return None


def parse_tabs_html(path: Path) -> list[tuple[str, str]]:
    """Extract links from tabs*.html file."""
    try:
        from bs4 import BeautifulSoup

        content = path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(content, "html.parser")
        links = []

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href.startswith(("http://", "https://")):
                continue

            # Get link text as title
            title = a.get_text().strip()
            if not title:
                title = Path(href).name
            if not title:
                title = "Article"

            links.append((title, href))

        return links
    except Exception as e:
        logger.error(f"Error parsing {path.name}: {e}")
        return []


def extract_urls_from_file(path: Path) -> list[tuple[str, str]]:
    """
    Extract URLs from file.
    Returns list of (title, url) tuples.
    """
    urls = []

    if path.suffix.lower() == ".md":
        content = path.read_text(encoding="utf-8", errors="ignore")
        url = extract_url_from_text(content)
        if url:
            urls.append((path.stem, url))

    elif path.name.lower().startswith("tabs") and path.suffix.lower() == ".html":
        links = parse_tabs_html(path)
        urls.extend(links)

    return urls


def load_tracker() -> dict:
    """Load sync tracker from file."""
    if TRACKER_FILE.exists():
        try:
            with open(TRACKER_FILE) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load tracker: {e}")

    return {
        "synced_files": [],
        "last_sync": None,
        "stats": {"total_synced": 0, "total_done": 0, "total_errors": 0},
    }


def save_tracker(tracker: dict) -> None:
    """Save sync tracker to file."""
    TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TRACKER_FILE, "w") as f:
        json.dump(tracker, f, indent=2)


def trigger_workflow(urls: list[str], titles: Optional[list[str]] = None) -> Optional[int]:
    """
    Trigger GitHub Actions workflow via API.
    Returns workflow run ID on success, None on failure.
    """
    config = load_config()
    token = get_github_token()

    # Get repo info from git config
    try:
        import subprocess

        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
        )
        repo_url = result.stdout.strip()
        # Extract owner/repo from URL
        if "github.com" in repo_url:
            parts = repo_url.split("github.com/")[1].replace(".git", "").split("/")
            owner, repo = parts[0], parts[1]
        else:
            logger.error(f"Could not parse repo from: {repo_url}")
            return None
    except Exception as e:
        logger.error(f"Failed to get repo info: {e}")
        return None

    workflow_id = config.get("sync", {}).get("github_workflow_id", "process-articles")

    # Prepare payload
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }

    payload = {
        "ref": "main",
        "inputs": {
            "urls": ",".join(urls),
            "titles": ",".join(titles) if titles else "",
            "tags": "",  # Can be extended later
        },
    }

    url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches"

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)

        if response.status_code == 204:
            logger.info(f"✓ Workflow triggered: {', '.join(urls)}")

            # Get workflow run ID from next API call
            # (GitHub doesn't return it immediately, so we'll fetch it)
            time.sleep(1)  # Wait a moment for workflow to appear
            return 1  # Placeholder
        else:
            logger.error(
                f"✗ Failed to trigger workflow: HTTP {response.status_code}"
            )
            if response.text:
                logger.error(f"  Response: {response.text}")
            return None

    except Exception as e:
        logger.error(f"✗ API error: {e}")
        return None


def mark_synced(tracker: dict, file_name: str, urls: list[str], workflow_id: Optional[int]) -> None:
    """Mark file as synced in tracker."""
    tracker["synced_files"].append(
        {
            "name": file_name,
            "urls": urls,
            "triggered_at": datetime.now(timezone.utc).isoformat(),
            "workflow_id": workflow_id,
            "status": "queued",
        }
    )
    tracker["last_sync"] = datetime.now(timezone.utc).isoformat()
    tracker["stats"]["total_synced"] += 1
    save_tracker(tracker)


class SyncHandler(FileSystemEventHandler):
    """Watch for file changes and sync to GitHub."""

    def __init__(self):
        self.recently_processed = {}

    def _should_process(self, src_path: str) -> bool:
        """Check if file should be processed."""
        path = Path(src_path)

        # Skip if not a file
        if not path.is_file():
            return False

        # Skip if in skip patterns
        if any(pattern in path.name for pattern in SKIP_PATTERNS):
            return False

        # Skip if recently processed (debounce)
        if src_path in self.recently_processed:
            if time.time() - self.recently_processed[src_path] < DEBOUNCE_TIMEOUT:
                return False

        # Skip if already in organized folders
        if any(
            folder in path.parts
            for folder in ("articles", "processed", "originals", "errors", "Other")
        ):
            return False

        # Only process .md and tabs*.html
        if path.suffix.lower() == ".md":
            return True
        if path.name.lower().startswith("tabs") and path.suffix.lower() == ".html":
            return True

        return False

    def on_created(self, event):
        """Handle file creation."""
        if self._should_process(event.src_path):
            self._process_file(event.src_path)

    def on_modified(self, event):
        """Handle file modification."""
        if self._should_process(event.src_path):
            self._process_file(event.src_path)

    def _process_file(self, src_path: str):
        """Process a file: extract URLs and trigger workflow."""
        path = Path(src_path)

        # Wait for file to be fully written
        time.sleep(2)

        if not path.exists():
            return

        logger.info(f"Processing: {path.name}")

        # Extract URLs
        url_tuples = extract_urls_from_file(path)
        if not url_tuples:
            logger.warning(f"No URLs found in {path.name}")
            return

        urls = [url for _, url in url_tuples]
        titles = [title for title, _ in url_tuples]

        # Trigger workflow
        workflow_id = trigger_workflow(urls, titles)

        # Track in sync_tracker.json
        tracker = load_tracker()
        mark_synced(tracker, path.name, urls, workflow_id)

        # Mark as processed
        self.recently_processed[src_path] = time.time()
        logger.info(f"✓ Synced {path.name} ({len(urls)} URL(s))")


def watch_folder(folder: Path) -> None:
    """Watch folder for changes."""
    if not folder.exists():
        logger.error(f"Folder not found: {folder}")
        sys.exit(1)

    logger.info(f"Starting sync watcher on: {folder}")
    logger.info("Watching for .md and tabs*.html files...")
    logger.info("Press Ctrl+C to stop")

    handler = SyncHandler()
    observer = Observer()
    observer.schedule(handler, str(folder), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping watcher...")
        observer.stop()
        observer.join()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Sync Nextcloud to GitHub")
    parser.add_argument("--watch", action="store_true", help="Watch folder for changes")
    parser.add_argument("--check", action="store_true", help="Check tracker status")
    args = parser.parse_args()

    if args.check:
        tracker = load_tracker()
        print(json.dumps(tracker, indent=2))
        return

    if args.watch:
        config = load_config()
        nextcloud_folder = Path(config.get("watch_folder", "~/Nextcloud/Notes")).expanduser()
        watch_folder(nextcloud_folder)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
