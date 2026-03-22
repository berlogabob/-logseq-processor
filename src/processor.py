import json
from pathlib import Path
from typing import List, Optional, Set, Tuple, TypedDict

from bs4 import BeautifulSoup

from .common import Config, ProcessingError, log_info, logger, validate_url
from .html_parser import fetch_and_extract
from .llm import get_article_metadata
from .metadata import build_content, create_fallback_metadata
from .utils import expand_url, get_domain, get_unique_path, is_processed, normalize_url
from .youtube import get_youtube_transcript, is_youtube

_processed_urls_cache: Optional[Set[str]] = None


class IngestResult(TypedDict):
    expanded_url: str
    normalized_url: str
    extracted_text: str
    is_youtube: bool
    source: str


def _load_processed_urls_cache(folder: Path) -> Set[str]:
    global _processed_urls_cache
    if _processed_urls_cache is not None:
        return _processed_urls_cache

    _processed_urls_cache = set()
    try:
        for file in folder.rglob("*.md"):
            if file.is_file():
                try:
                    content = file.read_text(encoding="utf-8", errors="ignore")
                    for line in content.split("\n"):
                        if line.startswith("url:: "):
                            url = line[6:].strip()
                            if url:
                                _processed_urls_cache.add(normalize_url(url))
                except Exception:
                    continue
    except Exception:
        pass
    return _processed_urls_cache


def _url_already_processed(url: str, folder: Path) -> bool:
    cache = _load_processed_urls_cache(folder)
    return normalize_url(url) in cache


def parse_tabs_html(path: Path) -> List[Tuple[str, str]]:
    links: List[Tuple[str, str]] = []
    try:
        soup = BeautifulSoup(
            path.read_text(encoding="utf-8", errors="ignore"), "html.parser"
        )
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href.startswith(("http://", "https://")) or not validate_url(href):
                continue
            txt = a.get_text().strip()
            if not txt:
                txt = Path(href).name
            if not txt:
                txt = "Article"
            links.append((txt, href))
        return links
    except Exception as e:
        logger.error("Error parsing %s: %s", path.name, e)
        return []


def process_article(
    url: str, title: str, model: str, force: bool = False
) -> Tuple[bool, ProcessingError]:
    """
    Process article from URL and save to Logseq notes.
    Returns: (success: bool, error_type: ProcessingError)
    """
    config = Config.get()
    articles_folder = config.get_articles_folder()
    articles_folder.mkdir(parents=True, exist_ok=True)

    if not validate_url(url):
        log_info(f"Invalid URL: {url[:80]}")
        return False, ProcessingError.INVALID_URL

    if _url_already_processed(url, articles_folder) and not force:
        return True, ProcessingError.UNKNOWN

    ingest, ingest_error = ingest_article(url, title, force=force)
    if not ingest:
        if ingest_error == ProcessingError.UNKNOWN:
            return True, ProcessingError.UNKNOWN
        return False, ingest_error

    source = ingest["source"]
    final_url = ingest["expanded_url"]
    log_info(f"Domain: {source}, Title: {title}")
    out_path = get_unique_path(title, articles_folder, source=source)
    log_info(f"Out path: {out_path.name}")

    if out_path.exists() and is_processed(out_path) and not force:
        return True, ProcessingError.UNKNOWN

    extracted = ingest["extracted_text"]
    is_yt = ingest["is_youtube"]
    error_type = ProcessingError.UNKNOWN

    if extracted and len(extracted) < config.content_min_length:
        logger.warning(
            f"Content short ({len(extracted)} chars, min: {config.content_min_length}): {final_url[:80]}"
        )

    if not extracted or len(extracted) < 10:
        logger.error(f"Content empty or too short: {final_url[:80]}")
        error_type = ProcessingError.EMPTY_CONTENT

    metadata = get_article_metadata(extracted or "", model, is_youtube=is_yt)
    if not metadata:
        metadata = create_fallback_metadata(final_url)
        error_type = ProcessingError.LLM_ERROR

    content = build_content(title, final_url, metadata, extracted or "", is_youtube=is_yt)
    out_path.write_text(content, encoding="utf-8")

    if _processed_urls_cache is not None:
        _processed_urls_cache.add(ingest["normalized_url"])

    log_info(f"Saved: {out_path.name}")

    if error_type == ProcessingError.EMPTY_CONTENT:
        return False, error_type
    return True, ProcessingError.UNKNOWN


def ingest_article(
    url: str, title: str, force: bool = False
) -> Tuple[Optional[IngestResult], ProcessingError]:
    config = Config.get()
    articles_folder = config.get_articles_folder()
    articles_folder.mkdir(parents=True, exist_ok=True)

    expanded_url = expand_url(url) or url
    if not validate_url(expanded_url):
        log_info(f"Invalid URL: {expanded_url[:80]}")
        return None, ProcessingError.INVALID_URL

    normalized_url = normalize_url(expanded_url)
    if _url_already_processed(normalized_url, articles_folder) and not force:
        return None, ProcessingError.UNKNOWN

    is_yt = is_youtube(expanded_url)
    extracted: Optional[str] = None
    error_type = ProcessingError.UNKNOWN

    try:
        if is_yt:
            extracted = get_youtube_transcript(expanded_url)
            if not extracted:
                extracted = f"Ссылка: {expanded_url}\n(Транскрипт не найден)"
                error_type = ProcessingError.EMPTY_CONTENT
        else:
            extracted = fetch_and_extract(expanded_url)
            if extracted is None:
                extracted = (
                    f"Ссылка: {expanded_url}\nЗаголовок: {title}\n(Не удалось извлечь текст)"
                )
                error_type = ProcessingError.PARSE_ERROR
    except Exception as e:
        logger.error(f"Network error for {expanded_url[:80]}: {e}")
        if "timeout" in str(e).lower():
            return None, ProcessingError.TIMEOUT
        return None, ProcessingError.NETWORK_ERROR

    if not extracted or len(extracted) < 10:
        logger.error(f"Content empty or too short: {expanded_url[:80]}")
        return None, ProcessingError.EMPTY_CONTENT

    if error_type != ProcessingError.UNKNOWN:
        return None, error_type

    return (
        {
            "expanded_url": expanded_url,
            "normalized_url": normalized_url,
            "extracted_text": extracted,
            "is_youtube": is_yt,
            "source": get_domain(expanded_url),
        },
        ProcessingError.UNKNOWN,
    )


def finalize_article(
    title: str,
    expanded_url: str,
    normalized_url: str,
    extracted_text: str,
    is_yt: bool,
    source: str,
    model: str,
) -> Tuple[bool, ProcessingError, Optional[Path]]:
    config = Config.get()
    articles_folder = config.get_articles_folder()
    articles_folder.mkdir(parents=True, exist_ok=True)

    out_path = get_unique_path(title, articles_folder, source=source)
    if out_path.exists() and is_processed(out_path):
        return True, ProcessingError.UNKNOWN, out_path

    error_type = ProcessingError.UNKNOWN
    metadata = get_article_metadata(extracted_text or "", model, is_youtube=is_yt)
    if not metadata:
        metadata = create_fallback_metadata(expanded_url)
        error_type = ProcessingError.LLM_ERROR

    content = build_content(title, expanded_url, metadata, extracted_text or "", is_youtube=is_yt)
    out_path.write_text(content, encoding="utf-8")

    if _processed_urls_cache is not None:
        _processed_urls_cache.add(normalized_url)

    if error_type == ProcessingError.LLM_ERROR:
        return False, error_type, out_path
    return True, ProcessingError.UNKNOWN, out_path
