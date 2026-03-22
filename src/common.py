import logging
import os
import sys
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Optional
from urllib.parse import urlparse

import yaml

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_FILE = PROJECT_ROOT / "config.yaml"

LOGS_HOME = Path.home() / ".logseq-processor"
LOGS_FOLDER = LOGS_HOME / "logs"


class ProcessingError(Enum):
    INVALID_URL = "invalid_url"
    NETWORK_ERROR = "network_error"
    PARSE_ERROR = "parse_error"
    LLM_ERROR = "llm_error"
    EMPTY_CONTENT = "empty_content"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"
    NO_URL_FOUND = "no_url_found"


class Config:
    _instance: Optional["Config"] = None
    _loaded: bool = False

    def __init__(self):
        self.model: str = "qwen3.5:9b"
        self.default_delay_seconds: int = 2
        self.max_retries: int = 3
        self.watch_folder: Path = Path.home() / "Nextcloud/Notes"
        self.rate_limit_delay_per_domain: float = 2.0
        self.rate_limit_delay_global: float = 1.0
        self.content_min_length: int = 100
        self.content_max_length: int = 8000
        self.http_retry_429_count: int = 3
        self.http_retry_429_backoff_seconds: float = 1.0
        self.llm_timeout_seconds: int = 30
        self.llm_temperature_attempts: list[float] = [0.05, 0.25, 0.50]
        self.llm_max_parallel_jobs: int = 1
        self.folders_articles: str = "articles"
        self.folders_processed: str = "processed"
        self.folders_originals: str = "originals"
        self.folders_errors: str = "errors"
        self.folders_other: str = "Other"
        self.queue_file: Path = LOGS_HOME / "queue.json"
        self.logging_level: str = "INFO"
        self.logging_folder: Path = LOGS_HOME / "logs"
        self.logging_retention_days: int = 7
        self.logging_console: bool = True
        self.queue_heartbeat_seconds: float = 10.0
        self.warmup_llm: bool = True

    @classmethod
    def get(cls) -> "Config":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._load()
        return cls._instance

    def _load(self):
        if self._loaded:
            return

        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            self._apply_dict(data)

        self._loaded = True

    def _apply_dict(self, data: dict):
        self.model = data.get("model", self.model)
        self.default_delay_seconds = data.get(
            "default_delay_seconds", self.default_delay_seconds
        )
        self.max_retries = data.get("max_retries", self.max_retries)
        self.warmup_llm = data.get("warmup_llm", self.warmup_llm)

        watch = data.get("watch_folder", "")
        if watch:
            self.watch_folder = Path(watch).expanduser().resolve()

        rate = data.get("rate_limit", {})
        self.rate_limit_delay_per_domain = rate.get(
            "delay_per_domain", self.rate_limit_delay_per_domain
        )
        self.rate_limit_delay_global = rate.get(
            "delay_global", self.rate_limit_delay_global
        )

        content = data.get("content", {})
        self.content_min_length = content.get("min_length", self.content_min_length)
        self.content_max_length = content.get("max_length", self.content_max_length)

        http = data.get("http", {})
        self.http_retry_429_count = http.get(
            "retry_429_count", self.http_retry_429_count
        )
        self.http_retry_429_backoff_seconds = http.get(
            "retry_429_backoff_seconds", self.http_retry_429_backoff_seconds
        )

        llm = data.get("llm", {})
        self.llm_timeout_seconds = llm.get("timeout_seconds", self.llm_timeout_seconds)
        self.llm_temperature_attempts = llm.get(
            "temperature_attempts", self.llm_temperature_attempts
        )
        self.llm_max_parallel_jobs = max(
            1, int(llm.get("max_parallel_jobs", self.llm_max_parallel_jobs))
        )

        folders = data.get("folders", {})
        self.folders_articles = folders.get("articles", self.folders_articles)
        self.folders_processed = folders.get("processed", self.folders_processed)
        self.folders_originals = folders.get("originals", self.folders_originals)
        self.folders_errors = folders.get("errors", self.folders_errors)
        self.folders_other = folders.get("other", self.folders_other)

        logging_cfg = data.get("logging", {})
        self.logging_level = logging_cfg.get("level", self.logging_level)
        log_folder = logging_cfg.get("folder", "")
        if log_folder:
            self.logging_folder = Path(log_folder).expanduser().resolve()
        self.logging_retention_days = logging_cfg.get(
            "retention_days", self.logging_retention_days
        )
        self.logging_console = logging_cfg.get("console", self.logging_console)
        self.queue_heartbeat_seconds = float(
            logging_cfg.get("queue_heartbeat_seconds", self.queue_heartbeat_seconds)
        )

    def get_articles_folder(self) -> Path:
        return self.watch_folder / self.folders_articles

    def get_processed_folder(self) -> Path:
        return self.watch_folder / self.folders_processed

    def get_originals_folder(self) -> Path:
        return self.watch_folder / self.folders_originals

    def get_errors_folder(self) -> Path:
        return self.watch_folder / self.folders_errors

    def get_other_folder(self) -> Path:
        return self.watch_folder / self.folders_other


def setup_logging() -> logging.Logger:
    config = Config.get()

    LOGS_FOLDER.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("logseq-processor")
    logger.setLevel(getattr(logging, config.logging_level.upper()))
    logger.handlers.clear()

    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    file_format = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")

    from logging.handlers import TimedRotatingFileHandler

    file_handler = TimedRotatingFileHandler(
        LOGS_FOLDER / "processor.log",
        when="midnight",
        interval=1,
        backupCount=config.logging_retention_days,
        encoding="utf-8",
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    if config.logging_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s %(message)s", datefmt="[%H:%M:%S]")
        )
        logger.addHandler(console_handler)

    return logger


logger = setup_logging()


class DomainRateLimiter:
    def __init__(self, delay_per_domain: float = 2.0, delay_global: float = 1.0):
        self.delay_domain = delay_per_domain
        self.delay_global = delay_global
        self.last_request_domain: dict[str, float] = {}
        self.last_request_global = 0.0
        self.lock = Lock()

    def wait(self, url: str) -> bool:
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]

        with self.lock:
            now = time.time()

            time_since_global = now - self.last_request_global
            if time_since_global < self.delay_global:
                time.sleep(self.delay_global - time_since_global)
                now = time.time()

            time_since_domain = now - self.last_request_domain.get(domain, 0)
            if time_since_domain < self.delay_domain:
                sleep_time = self.delay_domain - time_since_domain
                time.sleep(sleep_time)

            self.last_request_global = time.time()
            self.last_request_domain[domain] = time.time()
            return time_since_domain < self.delay_domain


rate_limiter: Optional[DomainRateLimiter] = None


def get_rate_limiter() -> DomainRateLimiter:
    global rate_limiter
    if rate_limiter is None:
        config = Config.get()
        rate_limiter = DomainRateLimiter(
            delay_per_domain=config.rate_limit_delay_per_domain,
            delay_global=config.rate_limit_delay_global,
        )
    return rate_limiter


def validate_url(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    if len(url) > 2048:
        return False
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except (ValueError, AttributeError):
        return False


def get_timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log_print(message: str, emoji: str = ""):
    prefix = f"[{get_timestamp()}]"
    if emoji:
        prefix += f" {emoji}"
    print(f"{prefix} {message}", flush=True)


_STAGE_COLORS = {
    "FILE": "\033[36m",   # cyan
    "QUEUE": "\033[33m",  # yellow
    "LLM": "\033[35m",    # magenta
    "SYSTEM": "\033[32m", # green
}
_ANSI_RESET = "\033[0m"


def _supports_color() -> bool:
    if os.getenv("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def log_stage(stage: str, message: str):
    ts = get_timestamp()
    stage_upper = stage.upper()
    marker = f"● {stage_upper}"
    if _supports_color():
        color = _STAGE_COLORS.get(stage_upper, "\033[37m")
        marker = f"{color}{marker}{_ANSI_RESET}"
    print(f"[{ts}] {marker} {message}", flush=True)


def log_info(message: str):
    logger.info(message)


def log_error(message: str):
    logger.error(message)


def log_warning(message: str):
    logger.warning(message)


def log_debug(message: str):
    logger.debug(message)


def warmup_llm(model: str) -> bool:
    try:
        from ollama import chat

        log_print(f"Warming up LLM ({model})...", "🔥")
        resp = chat(
            model=model,
            messages=[{"role": "user", "content": "Hi"}],
            options={"temperature": 0.1},
            stream=False,
        )
        log_print("LLM ready", "✓")
        return True
    except Exception as e:
        log_warning(f"LLM warmup failed: {e}")
        return False
