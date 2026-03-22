import re
import shutil
import time
from pathlib import Path
from typing import Optional, Tuple

import requests
from urllib.parse import urlparse

from .common import Config, ProcessingError, log_info, logger


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    if netloc.startswith("m."):
        netloc = netloc[2:]

    path = parsed.path.rstrip("/")
    if not path:
        path = "/"

    normalized = f"{parsed.scheme.lower()}://{netloc}{path}"

    normalized = re.sub(r":80(?=/|$)", "", normalized)
    normalized = re.sub(r":443(?=/|$)", "", normalized)

    if "#" in normalized:
        normalized = normalized.split("#")[0]

    query_params_to_keep = {"v", "p", "id", "q", "search"}
    parsed2 = urlparse(normalized)
    if parsed2.query:
        params = []
        for param in parsed2.query.split("&"):
            if "=" in param:
                key = param.split("=")[0]
                if key.lower() in query_params_to_keep:
                    params.append(param)
        if params:
            normalized = f"{normalized.split('?')[0]}?{'&'.join(params)}"
        else:
            normalized = normalized.split("?")[0]

    return normalized


def get_unique_path(title: str, folder: Path, source: str = "") -> Path:
    source = source.strip() if source else ""
    if source:
        formatted = f"{source} - {title}"
    else:
        formatted = title

    base = re.sub(r"[/\\:*?\"<>|]", "", formatted)[:150].strip().replace(" ", "-")
    base = re.sub(r"-+", "-", base).rstrip("-").lstrip("-")
    if not base:
        base = "Article"

    path = folder / (base + ".md")
    counter = 1
    while path.exists():
        path = folder / f"{base} ({counter}).md"
        counter += 1
    return path


def is_processed(path: Path) -> bool:
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8", errors="ignore")
    return "title::" in content and "type:: article" in content


def extract_url_from_text(text: str) -> Optional[str]:
    urls = re.findall(r"https?://[^\s<>\"'\)]+", text)
    for url in urls:
        url = url.rstrip(".,;:!?")
        if len(url) > 10:
            return url
    return None


def sanitize_filename(name: str, max_len: int = 80) -> str:
    cleaned = re.sub(r"[^A-Za-zА-Яа-я0-9\s\-]", "", name)[:max_len].strip()
    return cleaned.replace(" ", "-")


def get_error_suffix(
    error_type: ProcessingError, timestamp: Optional[int] = None
) -> str:
    if timestamp is None:
        timestamp = int(time.time())
    return f"_error_{error_type.value}_{timestamp}"


def move_to_folder(
    source: Path, target_folder: Path, error_suffix: Optional[str] = None
) -> Optional[Path]:
    target_folder.mkdir(parents=True, exist_ok=True)

    if error_suffix:
        name = source.stem + error_suffix + source.suffix
    else:
        name = source.name

    dest = target_folder / name
    counter = 1
    while dest.exists():
        if error_suffix:
            name = f"{source.stem}{error_suffix}_{counter}{source.suffix}"
        else:
            name = f"{source.stem}_{counter}{source.suffix}"
        dest = target_folder / name
        counter += 1

    try:
        shutil.move(str(source), str(dest))
        log_info(f"Moved: {source.name} → {dest}")
        return dest
    except Exception as e:
        logger.error(f"Failed to move {source.name} to {target_folder}: {e}")
        return None


def get_domain(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    if domain.startswith("m."):
        domain = domain[2:]
    return domain


def ensure_folders_exist():
    config = Config.get()
    folders = [
        config.get_articles_folder(),
        config.get_processed_folder(),
        config.get_originals_folder(),
        config.get_errors_folder(),
        config.get_other_folder(),
    ]
    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)


def count_non_empty_lines(path: Path) -> int:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        return sum(1 for line in content.splitlines() if line.strip())
    except Exception:
        return 999


def clean_json(raw: str) -> str:
    raw = re.sub(r"```json|```|json", "", raw, flags=re.DOTALL | re.I)
    raw = re.sub(r"```json|```|^json\s*", "", raw, flags=re.MULTILINE | re.IGNORECASE)
    start = raw.find("{")
    end = raw.rfind("}") + 1
    return raw[start:end] if start >= 0 and end > start else "{}"


def expand_url(url: str, timeout: int = 10, max_redirects: int = 5) -> Optional[str]:
    if not url:
        return None
    current = url
    session = requests.Session()
    session.max_redirects = max_redirects

    try:
        resp = session.head(current, allow_redirects=True, timeout=timeout)
        if resp.url:
            current = resp.url
    except requests.RequestException:
        try:
            resp = session.get(current, allow_redirects=True, timeout=timeout, stream=True)
            if resp.url:
                current = resp.url
            resp.close()
        except requests.RequestException:
            return None

    if not current.startswith(("http://", "https://")):
        return None
    return current
