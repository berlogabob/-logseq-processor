import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.pipeline_queue import ACTIVE_STATUSES, PipelineQueue


class PipelineQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "pipeline.db"
        self.queue = PipelineQueue(db_path=self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def _fetch_job(self, job_id: int) -> sqlite3.Row:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        self.assertIsNotNone(row)
        return row

    def test_enqueue_dedupes_by_normalized_url_for_active_statuses(self):
        for status in ACTIVE_STATUSES:
            with self.subTest(status=status):
                with tempfile.TemporaryDirectory() as temp_dir:
                    queue = PipelineQueue(db_path=Path(temp_dir) / "pipeline.db")
                    with patch("src.pipeline_queue.expand_url", side_effect=lambda u: u):
                        created = queue.enqueue(
                            "https://www.example.com/article/", "Original"
                        )
                        self.assertTrue(created)

                        job = queue.get_jobs("queued_ingest", limit=1)[0]
                        job_id = job["id"]

                        if status == "queued_llm":
                            queue.mark_ingested(
                                job_id=job_id,
                                expanded_url="https://example.com/article",
                                normalized_url="https://example.com/article",
                                extracted_text="text",
                                is_youtube=False,
                            )
                        elif status == "processing_llm":
                            queue.mark_ingested(
                                job_id=job_id,
                                expanded_url="https://example.com/article",
                                normalized_url="https://example.com/article",
                                extracted_text="text",
                                is_youtube=False,
                            )
                            queue.claim_jobs(
                                from_status="queued_llm",
                                to_status="processing_llm",
                                limit=1,
                            )
                        elif status == "llm_done":
                            queue.mark_ingested(
                                job_id=job_id,
                                expanded_url="https://example.com/article",
                                normalized_url="https://example.com/article",
                                extracted_text="text",
                                is_youtube=False,
                            )
                            queue.mark_llm_done(job_id=job_id, out_path="/tmp/out.md")

                        duplicate = queue.enqueue(
                            "https://example.com/article", "Duplicate"
                        )
                        self.assertFalse(duplicate)

                    with sqlite3.connect(Path(temp_dir) / "pipeline.db") as conn:
                        count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
                    self.assertEqual(count, 1)

    def test_mark_ingested_transitions_to_queued_llm(self):
        with patch("src.pipeline_queue.expand_url", return_value="https://example.com/a"):
            self.assertTrue(self.queue.enqueue("https://short/a", "Title"))

        job = self.queue.get_jobs("queued_ingest", limit=1)[0]
        self.queue.mark_ingested(
            job_id=job["id"],
            expanded_url="https://example.com/a",
            normalized_url="https://example.com/a",
            extracted_text="body",
            is_youtube=True,
        )

        updated = self._fetch_job(job["id"])
        self.assertEqual(updated["status"], "queued_llm")
        self.assertEqual(updated["attempts_ingest"], 1)
        self.assertEqual(updated["url_expanded"], "https://example.com/a")
        self.assertEqual(updated["url_normalized"], "https://example.com/a")
        self.assertEqual(updated["extracted_text"], "body")
        self.assertEqual(updated["is_youtube"], 1)

    def test_mark_llm_done_transitions_to_llm_done(self):
        with patch("src.pipeline_queue.expand_url", return_value="https://example.com/a"):
            self.assertTrue(self.queue.enqueue("https://short/a", "Title"))

        job = self.queue.get_jobs("queued_ingest", limit=1)[0]
        self.queue.mark_ingested(
            job_id=job["id"],
            expanded_url="https://example.com/a",
            normalized_url="https://example.com/a",
            extracted_text="body",
            is_youtube=False,
        )
        self.queue.mark_llm_done(job_id=job["id"], out_path="/tmp/result.md")

        updated = self._fetch_job(job["id"])
        self.assertEqual(updated["status"], "llm_done")
        self.assertEqual(updated["attempts_llm"], 1)
        self.assertEqual(updated["out_path"], "/tmp/result.md")
        self.assertIsNone(updated["error"])

    def test_mark_llm_failed_transitions_to_llm_failed(self):
        with patch("src.pipeline_queue.expand_url", return_value="https://example.com/a"):
            self.assertTrue(self.queue.enqueue("https://short/a", "Title"))

        job = self.queue.get_jobs("queued_ingest", limit=1)[0]
        self.queue.mark_ingested(
            job_id=job["id"],
            expanded_url="https://example.com/a",
            normalized_url="https://example.com/a",
            extracted_text="body",
            is_youtube=False,
        )
        self.queue.mark_llm_failed(
            job_id=job["id"],
            error="llm error",
            out_path="/tmp/partial.md",
        )

        updated = self._fetch_job(job["id"])
        self.assertEqual(updated["status"], "llm_failed")
        self.assertEqual(updated["attempts_llm"], 1)
        self.assertEqual(updated["out_path"], "/tmp/partial.md")
        self.assertEqual(updated["error"], "llm error")

    def test_claim_jobs_ignores_non_positive_limits(self):
        with patch("src.pipeline_queue.expand_url", side_effect=lambda u: u):
            self.assertTrue(self.queue.enqueue("https://example.com/limit", "Limit"))

        job = self.queue.get_jobs("queued_ingest", limit=1)[0]
        self.queue.mark_ingested(
            job_id=job["id"],
            expanded_url=job["url_original"],
            normalized_url=job["url_original"],
            extracted_text="body",
            is_youtube=False,
        )

        self.assertEqual(self.queue.claim_jobs("queued_llm", "processing_llm", limit=0), [])
        self.assertEqual(self.queue.claim_jobs("queued_llm", "processing_llm", limit=-1), [])

        remaining = self.queue.get_jobs("queued_llm", limit=10)
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["id"], job["id"])

    def test_claim_jobs_moves_status_atomically(self):
        with patch("src.pipeline_queue.expand_url", side_effect=lambda u: u):
            self.assertTrue(self.queue.enqueue("https://example.com/1", "One"))
            self.assertTrue(self.queue.enqueue("https://example.com/2", "Two"))
            self.assertTrue(self.queue.enqueue("https://example.com/3", "Three"))

        queued = self.queue.get_jobs("queued_ingest", limit=3)
        for job in queued:
            self.queue.mark_ingested(
                job_id=job["id"],
                expanded_url=job["url_original"],
                normalized_url=job["url_original"],
                extracted_text="body",
                is_youtube=False,
            )

        claimed = self.queue.claim_jobs("queued_llm", "processing_llm", limit=2)
        self.assertEqual(len(claimed), 2)
        self.assertTrue(all(job["status"] == "processing_llm" for job in claimed))

        remaining = self.queue.get_jobs("queued_llm", limit=10)
        self.assertEqual(len(remaining), 1)

        claimed_again = self.queue.claim_jobs("queued_llm", "processing_llm", limit=10)
        self.assertEqual(len(claimed_again), 1)

        claimed_none = self.queue.claim_jobs("queued_llm", "processing_llm", limit=10)
        self.assertEqual(claimed_none, [])


if __name__ == "__main__":
    unittest.main()
