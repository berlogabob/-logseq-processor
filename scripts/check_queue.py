#!/usr/bin/env python3
"""
Query and display queue status from queue/status.json.
Useful for monitoring processing progress.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


def load_status(queue_dir: Optional[Path] = None) -> dict:
    """Load status.json."""
    if queue_dir is None:
        queue_dir = Path('queue')
    
    status_file = Path(queue_dir) / 'status.json'
    
    if not status_file.exists():
        return {
            'queued': [],
            'processing': [],
            'done': [],
            'error': [],
            'last_update': None,
            'stats': {
                'total_queued': 0,
                'total_processed': 0,
                'total_errors': 0
            }
        }
    
    return json.loads(status_file.read_text())


def format_timestamp(iso_string: Optional[str]) -> str:
    """Format ISO timestamp for display."""
    if not iso_string:
        return "never"
    
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return iso_string


def format_url(url: str, max_len: int = 60) -> str:
    """Truncate URL for display."""
    if len(url) > max_len:
        return url[:max_len-3] + "..."
    return url


def print_queue_status(status: dict) -> None:
    """Pretty-print queue status."""
    print("=" * 80)
    print("QUEUE STATUS")
    print("=" * 80)
    
    # Stats
    stats = status.get('stats', {})
    print(f"\nStats:")
    print(f"  Total Queued: {stats.get('total_queued', 0)}")
    print(f"  Total Processed: {stats.get('total_processed', 0)}")
    print(f"  Total Errors: {stats.get('total_errors', 0)}")
    print(f"  Last Update: {format_timestamp(status.get('last_update'))}")
    
    # Pending
    queued = status.get('queued', [])
    if queued:
        print(f"\n⏳ PENDING ({len(queued)} items):")
        for i, item in enumerate(queued, 1):
            url = item.get('url', 'unknown')
            queued_at = format_timestamp(item.get('queued_at'))
            title = item.get('title', '')
            print(f"\n  {i}. {format_url(url)}")
            if title:
                print(f"     Title: {title}")
            print(f"     Queued: {queued_at}")
            print(f"     File: {item.get('file', 'unknown')}")
    
    # Processing
    processing = status.get('processing', [])
    if processing:
        print(f"\n⚙️  PROCESSING ({len(processing)} items):")
        for i, item in enumerate(processing, 1):
            url = item.get('url', 'unknown')
            started_at = format_timestamp(item.get('started_at'))
            print(f"\n  {i}. {format_url(url)}")
            print(f"     Started: {started_at}")
    
    # Done
    done = status.get('done', [])
    if done:
        print(f"\n✓ COMPLETED ({len(done)} items):")
        for i, item in enumerate(done, 1):
            url = item.get('url', 'unknown')
            completed_at = format_timestamp(item.get('completed_at'))
            output_file = item.get('output_file', 'unknown')
            print(f"\n  {i}. {format_url(url)}")
            print(f"     Completed: {completed_at}")
            print(f"     Output: {output_file}")
    
    # Errors
    errors = status.get('error', [])
    if errors:
        print(f"\n✗ ERRORS ({len(errors)} items):")
        for i, item in enumerate(errors, 1):
            url = item.get('url', 'unknown')
            error_msg = item.get('error', 'unknown')
            error_time = format_timestamp(item.get('error_at'))
            print(f"\n  {i}. {format_url(url)}")
            print(f"     Error: {error_msg}")
            print(f"     Time: {error_time}")
    
    print("\n" + "=" * 80)


def print_queue_summary(status: dict) -> None:
    """Print summary of queue."""
    queued_count = len(status.get('queued', []))
    processing_count = len(status.get('processing', []))
    done_count = len(status.get('done', []))
    error_count = len(status.get('error', []))
    
    print(f"Queue Summary:")
    print(f"  Pending: {queued_count}")
    print(f"  Processing: {processing_count}")
    print(f"  Completed: {done_count}")
    print(f"  Errors: {error_count}")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Check queue status'
    )
    parser.add_argument(
        '--queue-dir',
        default='queue',
        help='Queue directory (default: queue)'
    )
    parser.add_argument(
        '--summary',
        action='store_true',
        help='Show summary only'
    )
    parser.add_argument(
        '--pending',
        action='store_true',
        help='Show pending items only'
    )
    parser.add_argument(
        '--errors',
        action='store_true',
        help='Show errors only'
    )
    
    args = parser.parse_args()
    
    # Load status
    try:
        status = load_status(args.queue_dir)
    except Exception as e:
        print(f"Error loading status: {e}")
        sys.exit(1)
    
    # Display
    if args.summary:
        print_queue_summary(status)
    elif args.pending:
        queued = status.get('queued', [])
        if queued:
            print(f"Pending items ({len(queued)}):")
            for item in queued:
                print(f"  {item.get('url')}")
        else:
            print("No pending items")
    elif args.errors:
        errors = status.get('error', [])
        if errors:
            print(f"Error items ({len(errors)}):")
            for item in errors:
                print(f"  {item.get('url')}: {item.get('error')}")
        else:
            print("No error items")
    else:
        print_queue_status(status)
