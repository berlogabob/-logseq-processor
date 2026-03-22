import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .common import LOGS_HOME
from .utils import expand_url, normalize_url


ACTIVE_STATUSES = (
    "queued_ingest",
    "queued_llm",
    "llm_done",
)


class PipelineQueue:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or (LOGS_HOME / "pipeline.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_file TEXT,
                    title TEXT NOT NULL,
                    url_original TEXT NOT NULL,
                    url_expanded TEXT,
                    url_normalized TEXT,
                    status TEXT NOT NULL,
                    extracted_text TEXT,
                    is_youtube INTEGER NOT NULL DEFAULT 0,
                    attempts_ingest INTEGER NOT NULL DEFAULT 0,
                    attempts_llm INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    out_path TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_url_normalized ON jobs(url_normalized)"
            )

    def enqueue(self, url: str, title: str, source_file: str | None = None) -> bool:
        expanded = expand_url(url) or url
        normalized = normalize_url(expanded)

        with self._connect() as conn:
            exists = conn.execute(
                """
                SELECT 1
                FROM jobs
                WHERE url_normalized = ?
                  AND status IN (?, ?, ?)
                LIMIT 1
                """,
                (normalized, *ACTIVE_STATUSES),
            ).fetchone()
            if exists:
                return False

            now = datetime.now().isoformat()
            conn.execute(
                """
                INSERT INTO jobs (
                    source_file, title, url_original, url_expanded, url_normalized,
                    status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'queued_ingest', ?, ?)
                """,
                (source_file, title, url, expanded, normalized, now, now),
            )
        return True

    def get_jobs(self, status: str, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM jobs
                WHERE status = ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (status, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_ingested(
        self,
        job_id: int,
        expanded_url: str,
        normalized_url: str,
        extracted_text: str,
        is_youtube: bool,
    ):
        now = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = 'queued_llm',
                    url_expanded = ?,
                    url_normalized = ?,
                    extracted_text = ?,
                    is_youtube = ?,
                    attempts_ingest = attempts_ingest + 1,
                    error = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (expanded_url, normalized_url, extracted_text, int(is_youtube), now, job_id),
            )

    def mark_ingest_failed(self, job_id: int, error: str):
        now = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = 'ingest_failed',
                    attempts_ingest = attempts_ingest + 1,
                    error = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (error, now, job_id),
            )

    def mark_llm_done(self, job_id: int, out_path: str):
        now = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = 'llm_done',
                    attempts_llm = attempts_llm + 1,
                    out_path = ?,
                    error = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (out_path, now, job_id),
            )

    def mark_llm_failed(self, job_id: int, error: str, out_path: str | None = None):
        now = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = 'llm_failed',
                    attempts_llm = attempts_llm + 1,
                    out_path = COALESCE(?, out_path),
                    error = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (out_path, error, now, job_id),
            )

    def mark_skipped(self, job_id: int, reason: str):
        now = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = 'llm_done',
                    error = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (reason, now, job_id),
            )

    def get_stats(self) -> dict[str, int]:
        result: dict[str, int] = {}
        with self._connect() as conn:
            for row in conn.execute(
                "SELECT status, COUNT(*) AS n FROM jobs GROUP BY status"
            ).fetchall():
                result[row["status"]] = row["n"]
        return result
