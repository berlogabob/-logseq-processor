#!/usr/bin/env python3
"""
Pull processed articles from GitHub and sync to Nextcloud.

Periodically checks GitHub for new articles and syncs them
back to the Nextcloud folder.

Usage:
    python scripts/pull_processed_articles.py --daemon    # Run forever
    python scripts/pull_processed_articles.py --once       # Run once
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

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
TRACKER_FILE = Path.home() / ".logseq-processor" / "sync_tracker.json"


def load_config() -> dict:
    """Load config.yaml from project root."""
    config_path = Path(__file__).parent.parent / "config.yaml"
    if not config_path.exists():
        logger.error(f"config.yaml not found at {config_path}")
        sys.exit(1)
    with open(config_path) as f:
        return yaml.safe_load(f)


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


def run_git_command(cmd: list[str], cwd: Path) -> tuple[bool, str]:
    """Run a git command and return (success, output)."""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


def git_pull(repo_path: Path) -> bool:
    """Run git pull and return success status."""
    logger.info("Running git fetch...")
    success, output = run_git_command(["git", "fetch", "origin"], repo_path)
    if not success:
        logger.warning(f"git fetch failed: {output}")

    logger.info("Running git pull...")
    success, output = run_git_command(["git", "pull", "origin", "main"], repo_path)
    if success:
        logger.info("✓ git pull successful")
        return True
    else:
        logger.warning(f"git pull failed: {output}")
        return False


def get_new_articles(articles_path: Path) -> list[Path]:
    """Get new markdown files from articles folder."""
    if not articles_path.exists():
        return []

    articles = []
    for file in articles_path.glob("*.md"):
        if file.is_file():
            articles.append(file)

    return articles


def sync_articles_to_nextcloud(
    articles_path: Path, nextcloud_articles_path: Path
) -> int:
    """
    Sync articles from repo to Nextcloud.
    Returns number of synced articles.
    """
    if not articles_path.exists():
        logger.warning(f"articles/ folder not found: {articles_path}")
        return 0

    nextcloud_articles_path.mkdir(parents=True, exist_ok=True)
    synced_count = 0

    for article in get_new_articles(articles_path):
        try:
            dest = nextcloud_articles_path / article.name
            shutil.copy2(article, dest)
            logger.info(f"✓ Synced: {article.name} → {nextcloud_articles_path.name}/")
            synced_count += 1
        except Exception as e:
            logger.error(f"Failed to sync {article.name}: {e}")

    return synced_count


def update_tracker_complete(tracker: dict, synced_count: int) -> None:
    """Update tracker to mark sync as complete."""
    tracker["last_pull_sync"] = datetime.now(timezone.utc).isoformat()
    tracker["stats"]["total_done"] += synced_count

    # Update status of synced files
    for item in tracker["synced_files"]:
        if item.get("status") == "queued":
            item["status"] = "done"
            item["completed_at"] = datetime.now(timezone.utc).isoformat()

    save_tracker(tracker)


def sync_once(repo_path: Path, nextcloud_folder: Path) -> bool:
    """Run sync once and return success status."""
    logger.info("=" * 70)
    logger.info("Starting pull sync...")
    logger.info("=" * 70)

    # Git pull
    if not git_pull(repo_path):
        logger.warning("git pull failed, continuing with local state...")

    # Sync articles
    articles_path = repo_path / "articles"
    nextcloud_articles_path = nextcloud_folder / "articles"

    synced_count = sync_articles_to_nextcloud(articles_path, nextcloud_articles_path)

    if synced_count > 0:
        logger.info(f"✓ Synced {synced_count} article(s)")
        tracker = load_tracker()
        update_tracker_complete(tracker, synced_count)
    else:
        logger.info("No new articles to sync")

    logger.info("=" * 70)
    return True


def daemon_mode(repo_path: Path, nextcloud_folder: Path, interval: int) -> None:
    """Run sync in daemon mode (periodically)."""
    logger.info(f"Starting pull sync daemon (interval: {interval}s)")
    logger.info("Press Ctrl+C to stop")

    try:
        while True:
            sync_once(repo_path, nextcloud_folder)
            logger.info(f"Sleeping for {interval} seconds...")
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Stopping daemon...")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Pull processed articles from GitHub")
    parser.add_argument(
        "--daemon", action="store_true", help="Run as daemon (continuous)"
    )
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument(
        "--interval", type=int, default=300, help="Daemon check interval (seconds)"
    )
    args = parser.parse_args()

    config = load_config()
    repo_path = Path(__file__).parent.parent
    nextcloud_folder = Path(
        config.get("watch_folder", "~/Nextcloud/Notes")
    ).expanduser()

    if not repo_path.exists():
        logger.error(f"Repository not found: {repo_path}")
        sys.exit(1)

    if not nextcloud_folder.exists():
        logger.error(f"Nextcloud folder not found: {nextcloud_folder}")
        sys.exit(1)

    if args.daemon:
        daemon_mode(repo_path, nextcloud_folder, args.interval)
    elif args.once:
        sync_once(repo_path, nextcloud_folder)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
