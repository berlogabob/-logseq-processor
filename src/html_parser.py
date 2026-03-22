import time
from typing import Optional

import requests
import trafilatura

from .common import Config, get_rate_limiter, logger, validate_url

_session = requests.Session()
_session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; LogseqProcessor/1.0)"})

MAX_CONTENT_SIZE = 10 * 1024 * 1024


def fetch_html(url: str, timeout: int = 15) -> Optional[str]:
    if not validate_url(url):
        logger.error("Invalid URL provided: %s", url[:100])
        return None

    rate_limiter = get_rate_limiter()
    rate_limiter.wait(url)

    try:
        html = trafilatura.fetch_url(url)
        if html:
            logger.info("Fetched via trafilatura: %s", url[:80])
            return html
        logger.warning("Trafilatura empty: %s", url[:80])
    except Exception as e:
        logger.warning("Trafilatura failed: %s. Using requests...", e)

    try:
        config = Config.get()
        retry_count = max(0, int(config.http_retry_429_count))
        base_backoff = max(0.0, float(config.http_retry_429_backoff_seconds))
        max_attempts = retry_count + 1

        for attempt in range(max_attempts):
            response = _session.get(url, timeout=timeout)
            if response.status_code == 429 and attempt < max_attempts - 1:
                backoff = base_backoff * (2**attempt)
                logger.warning(
                    "HTTP 429 for %s (attempt %d/%d), retrying in %.2fs",
                    url[:80],
                    attempt + 1,
                    max_attempts,
                    backoff,
                )
                response.close()
                if backoff > 0:
                    time.sleep(backoff)
                continue

            response.raise_for_status()
            content = response.text
            if len(content) > MAX_CONTENT_SIZE:
                logger.warning("Content truncated (%d bytes)", len(content))
                content = content[:MAX_CONTENT_SIZE]
            logger.info("Fetched via requests: %s", url[:80])
            return content
    except requests.RequestException as e:
        logger.error("Requests failed: %s", e)
        return None


def extract_text_from_html(html: str) -> Optional[str]:
    try:
        result = trafilatura.extract(
            html,
            output_format="markdown",
            include_links=True,
            favor_precision=True,
        )
        if result:
            logger.info("Extracted %d chars from HTML", len(result))
        else:
            logger.warning("No content extracted from HTML")
        return result
    except Exception as e:
        logger.error("Failed to extract text from HTML: %s", e)
        return None


def fetch_and_extract(url: str, timeout: int = 15) -> Optional[str]:
    html = fetch_html(url, timeout=timeout)
    if html:
        return extract_text_from_html(html)
    return None
