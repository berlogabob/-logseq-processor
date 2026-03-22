from src.main import QueueHeartbeat


class _FakePipeline:
    def __init__(self, stats):
        self._stats = stats

    def get_stats(self):
        return self._stats


def test_snapshot_defaults_missing_statuses_to_zero():
    heartbeat = QueueHeartbeat(interval_seconds=10)
    heartbeat.pipeline = _FakePipeline({"queued_ingest": 2, "queued_llm": 1})
    assert heartbeat._snapshot() == (2, 1, 0, 0, 0)


def test_snapshot_collects_all_queue_summary_fields():
    heartbeat = QueueHeartbeat(interval_seconds=10)
    heartbeat.pipeline = _FakePipeline(
        {
            "queued_ingest": 3,
            "queued_llm": 4,
            "llm_done": 5,
            "llm_failed": 1,
            "ingest_failed": 2,
        }
    )
    assert heartbeat._snapshot() == (3, 4, 5, 1, 2)
