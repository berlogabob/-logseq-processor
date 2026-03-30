#!/usr/bin/env python3
"""
Convert URLs and metadata to markdown queue files for processing.
Used by GitHub Actions to generate queue stubs from workflow input.
"""

import json
import sys
from datetime import datetime, timezone
from hashlib import md5
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

# Try to import validate_urls, fallback if in scripts directory
try:
    from validate_urls import validate_url
except ImportError:
    # If running from scripts directory, add parent to path
    sys.path.insert(0, str(Path(__file__).parent))
    from validate_urls import validate_url


def get_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')
        return domain
    except Exception:
        return 'unknown'


def url_checksum(url: str) -> str:
    """Generate short checksum for URL to avoid collisions."""
    return md5(url.encode()).hexdigest()[:8]


def create_queue_markdown(
    url: str,
    title: Optional[str] = None,
    tags: Optional[list[str]] = None,
    force: bool = False
) -> str:
    """
    Create markdown stub for queue.
    
    Args:
        url: Article URL
        title: Optional article title
        tags: Optional list of tags
        force: Whether to force reprocessing
        
    Returns:
        Markdown content as string
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Build metadata
    lines = [
        f"url:: {url}",
        f"queued_at:: {timestamp}",
    ]
    
    if title:
        lines.append(f"title:: {title}")
    
    if tags:
        tags_str = ", ".join(tags) if isinstance(tags, list) else tags
        lines.append(f"tags:: {tags_str}")
    
    if force:
        lines.append("force:: true")
    
    # Logseq format: property lines (no bullets)
    return "\n".join(lines) + "\n"


def generate_queue_filename(url: str) -> str:
    """Generate unique filename for queue item."""
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    domain = get_domain(url)
    checksum = url_checksum(url)
    return f"pending_{timestamp}_{domain}_{checksum}.md"


def queue_urls(
    urls: list[str],
    titles: Optional[list[str]] = None,
    tags: Optional[list[str]] = None,
    force: bool = False,
    queue_dir: Optional[Path] = None,
    check_reachable: bool = False
) -> dict:
    """
    Queue a batch of URLs for processing.
    
    Args:
        urls: List of URLs to queue
        titles: Optional list of titles (one per URL)
        tags: Optional list of tags (applies to all URLs)
        force: Force reprocessing flag
        queue_dir: Directory to write queue files (default: ./queue)
        check_reachable: Validate URL reachability
        
    Returns:
        Dict with results: queued, failed, file_mapping
    """
    if queue_dir is None:
        queue_dir = Path('queue')
    
    queue_dir = Path(queue_dir)
    queue_dir.mkdir(parents=True, exist_ok=True)
    
    queued = []
    failed = []
    file_mapping = {}
    
    for i, url in enumerate(urls):
        # Validate URL
        is_valid, error = validate_url(url, check_reachable=check_reachable)
        if not is_valid:
            failed.append({
                'url': url,
                'error': error
            })
            continue
        
        # Get title for this URL
        title = None
        if titles and i < len(titles):
            title = titles[i]
        
        # Generate filename and content
        filename = generate_queue_filename(url)
        content = create_queue_markdown(url, title, tags, force)
        
        # Write file
        filepath = queue_dir / filename
        try:
            filepath.write_text(content)
            
            queued.append({
                'url': url,
                'file': filename,
                'title': title,
                'queued_at': datetime.now(timezone.utc).isoformat()
            })
            file_mapping[url] = filename
        except Exception as e:
            failed.append({
                'url': url,
                'error': f"Failed to write file: {e}"
            })
    
    return {
        'queued': queued,
        'failed': failed,
        'file_mapping': file_mapping,
        'queued_count': len(queued),
        'failed_count': len(failed),
        'total': len(urls)
    }


def update_status_json(
    queue_dir: Optional[Path] = None,
    queued_items: Optional[list[dict]] = None
) -> None:
    """
    Update queue/status.json with new queued items.
    
    Args:
        queue_dir: Directory containing status.json
        queued_items: List of queued item dicts
    """
    if queue_dir is None:
        queue_dir = Path('queue')
    
    queue_dir = Path(queue_dir)
    status_file = queue_dir / 'status.json'
    
    # Load existing status
    if status_file.exists():
        status = json.loads(status_file.read_text())
    else:
        status = {
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
    
    # Add new items
    if queued_items:
        status['queued'].extend(queued_items)
        status['stats']['total_queued'] += len(queued_items)
    
    status['last_update'] = datetime.now(timezone.utc).isoformat()
    
    # Write updated status
    status_file.write_text(json.dumps(status, indent=2))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: queue_to_markdown.py <url1>[,<url2>...] [--titles title1,title2,...] [--tags tag1,tag2,...] [--force] [--check-reachable] [--queue-dir DIR]")
        print("\nExample:")
        print('  python queue_to_markdown.py "https://example.com/article,https://other.com/post" \\')
        print('    --titles "Article Title,Other Title" --tags python,ai --check-reachable')
        sys.exit(1)
    
    # Parse arguments
    urls_input = sys.argv[1]
    titles = None
    tags = None
    force = False
    check_reachable = False
    queue_dir = None
    
    for i in range(2, len(sys.argv)):
        arg = sys.argv[i]
        if arg == '--force':
            force = True
        elif arg == '--check-reachable':
            check_reachable = True
        elif arg.startswith('--titles='):
            titles = arg.split('=', 1)[1].split(',')
        elif arg.startswith('--tags='):
            tags = arg.split('=', 1)[1].split(',')
        elif arg.startswith('--queue-dir='):
            queue_dir = arg.split('=', 1)[1]
    
    # Parse URLs
    urls = [u.strip() for u in urls_input.split(',')]
    
    # Default queue_dir to parent of scripts if not specified
    if queue_dir is None:
        queue_dir = Path(__file__).parent.parent / 'queue'
    
    # Queue
    result = queue_urls(
        urls,
        titles=titles,
        tags=tags,
        force=force,
        queue_dir=queue_dir,
        check_reachable=check_reachable
    )
    
    # Update status
    if result['queued']:
        update_status_json(queue_dir=queue_dir, queued_items=result['queued'])
    
    # Output
    print(f"Queued: {result['queued_count']}, Failed: {result['failed_count']}")
    
    if result['queued']:
        print("\n✓ Queued URLs:")
        for item in result['queued']:
            print(f"  {item['url']}")
            print(f"    → {item['file']}")
    
    if result['failed']:
        print("\n✗ Failed URLs:")
        for item in result['failed']:
            print(f"  {item['url']}: {item['error']}")
    
    sys.exit(0 if result['failed_count'] == 0 else 1)
