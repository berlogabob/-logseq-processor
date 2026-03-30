#!/usr/bin/env python3
"""
URL validation utilities for GitHub Actions workflows.
Provides regex validation and optional HTTP reachability checks.
"""

import re
import sys
from typing import Optional
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    requests = None


def validate_url_format(url: str) -> tuple[bool, Optional[str]]:
    """
    Validate URL format using regex.
    
    Args:
        url: URL string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Simple but comprehensive URL regex
    url_pattern = re.compile(
        r'^https?://'  # http or https
        r'(?:(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP address
        r'(?::\d+)?'  # optional port
        r'(?:/[^\s]*)?$',  # optional path
        re.IGNORECASE
    )
    
    url = url.strip()
    if not url:
        return False, "URL is empty"
    
    if not url_pattern.match(url):
        return False, f"Invalid URL format: {url}"
    
    # Additional checks
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return False, "URL missing hostname"
    except Exception as e:
        return False, f"URL parse error: {e}"
    
    return True, None


def validate_url_reachable(url: str, timeout: int = 5) -> tuple[bool, Optional[str]]:
    """
    Check if URL is reachable via HTTP HEAD request.
    
    Args:
        url: URL to check
        timeout: Request timeout in seconds
        
    Returns:
        Tuple of (is_reachable, error_message)
    """
    if requests is None:
        return True, None  # Skip if requests not available
    
    try:
        response = requests.head(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={'User-Agent': 'logseq-processor/1.0'}
        )
        
        if response.status_code >= 400:
            return False, f"HTTP {response.status_code} - server error"
        
        return True, None
    except requests.exceptions.Timeout:
        return False, "Request timeout"
    except requests.exceptions.ConnectionError:
        return False, "Connection failed"
    except Exception as e:
        return False, f"Reachability check failed: {e}"


def validate_url(
    url: str,
    check_reachable: bool = False,
    timeout: int = 5
) -> tuple[bool, Optional[str]]:
    """
    Comprehensive URL validation.
    
    Args:
        url: URL to validate
        check_reachable: Whether to perform HTTP HEAD check
        timeout: Request timeout for reachability check
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # First check format
    is_valid, error = validate_url_format(url)
    if not is_valid:
        return False, error
    
    # Optionally check reachability
    if check_reachable:
        is_reachable, error = validate_url_reachable(url, timeout)
        if not is_reachable:
            return False, error
    
    return True, None


def validate_urls_batch(
    urls: list[str],
    check_reachable: bool = False,
    timeout: int = 5
) -> dict:
    """
    Validate a batch of URLs.
    
    Args:
        urls: List of URLs to validate
        check_reachable: Whether to perform HTTP HEAD checks
        timeout: Request timeout for reachability checks
        
    Returns:
        Dict with 'valid' and 'invalid' lists
    """
    valid = []
    invalid = []
    
    for url in urls:
        is_valid, error = validate_url(url, check_reachable, timeout)
        if is_valid:
            valid.append(url)
        else:
            invalid.append((url, error))
    
    return {
        'valid': valid,
        'invalid': invalid,
        'valid_count': len(valid),
        'invalid_count': len(invalid),
        'total': len(urls)
    }


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: validate_urls.py <url1> [url2] ... [--check-reachable] [--timeout N]")
        sys.exit(1)
    
    # Parse arguments
    urls = []
    check_reachable = False
    timeout = 5
    
    for arg in sys.argv[1:]:
        if arg == '--check-reachable':
            check_reachable = True
        elif arg.startswith('--timeout'):
            timeout = int(arg.split('=')[1])
        else:
            urls.append(arg)
    
    # Validate
    result = validate_urls_batch(urls, check_reachable, timeout)
    
    # Output
    print(f"Valid: {result['valid_count']}, Invalid: {result['invalid_count']}")
    
    if result['valid']:
        print("\n✓ Valid URLs:")
        for url in result['valid']:
            print(f"  {url}")
    
    if result['invalid']:
        print("\n✗ Invalid URLs:")
        for url, error in result['invalid']:
            print(f"  {url}: {error}")
    
    sys.exit(0 if result['invalid_count'] == 0 else 1)
