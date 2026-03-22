#!/usr/bin/env python3

import argparse
import concurrent.futures
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .common import (
    Config,
    ProcessingError,
    get_timestamp,
    log_error,
    log_print,
    log_stage,
    logger,
    warmup_llm,
)
from .pipeline_queue import PipelineQueue
from .processor import (
    finalize_article,
    ingest_article,
    parse_tabs_html,
    process_article,
)
from .utils import (
    count_non_empty_lines,
    ensure_folders_exist,
    extract_url_from_text,
    get_domain,
    get_error_suffix,
    move_to_folder,
)

DEBOUNCE_TIMEOUT = 30
SKIP_PATTERNS = (".tmp", ".sync-conflict", "~", ".part", ".crdownload", ".icloud")


class QueueManager:
    def __init__(self):
        self.queue_file = Config.get().queue_file
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        self.data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if self.queue_file.exists():
            try:
                with open(self.queue_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"version": 1, "active_queue": None, "queues": {}}

    def _save(self):
        with open(self.queue_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def create_queue(self, source_file: str, links: list[dict]) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        queue_id = f"{Path(source_file).stem}_{timestamp}"

        items = []
        for link in links:
            items.append(
                {
                    "url": link["url"],
                    "title": link["title"],
                    "status": "pending",
                    "attempts": 0,
                    "error": None,
                    "processed_at": None,
                }
            )

        self.data["queues"][queue_id] = {
            "source_file": source_file,
            "created": datetime.now().isoformat(),
            "total": len(items),
            "completed": 0,
            "errors": 0,
            "items": items,
        }
        self.data["active_queue"] = queue_id
        self._save()
        return queue_id

    def get_active_queue(self) -> Optional[dict]:
        if not self.data["active_queue"]:
            return None
        return self.data["queues"].get(self.data["active_queue"])

    def get_pending_items(self) -> list[dict]:
        queue = self.get_active_queue()
        if not queue:
            return []
        return [item for item in queue["items"] if item["status"] == "pending"]

    def mark_completed(self, url: str):
        queue = self.get_active_queue()
        if not queue:
            return
        for item in queue["items"]:
            if item["url"] == url:
                item["status"] = "done"
                item["processed_at"] = datetime.now().isoformat()
                queue["completed"] += 1
                break
        self._save()

    def mark_error(self, url: str, error: str):
        queue = self.get_active_queue()
        if not queue:
            return
        for item in queue["items"]:
            if item["url"] == url:
                item["status"] = "error"
                item["error"] = error
                queue["errors"] += 1
                break
        self._save()

    def get_stats(self) -> tuple[int, int, int]:
        queue = self.get_active_queue()
        if not queue:
            return 0, 0, 0
        return queue["total"], queue["completed"], queue["errors"]

    def clear_active(self):
        if self.data["active_queue"]:
            queue = self.data["queues"].get(self.data["active_queue"])
            if queue:
                has_pending = any(
                    item["status"] == "pending" for item in queue["items"]
                )
                if not has_pending:
                    self.data["active_queue"] = None
                    self._save()


def process_tabs_file(
    path: Path,
    model: str,
    queue: QueueManager,
    pipeline: PipelineQueue | None = None,
    worker_mode: str = "all",
):
    original_path = path
    log_print(f"Processing tabs: {path.name}", "📑")

    links = parse_tabs_html(path)
    if not links:
        log_print(f"No links found in: {path.name}", "⚠️")
        config = Config.get()
        move_to_folder(
            path,
            config.get_errors_folder(),
            get_error_suffix(ProcessingError.PARSE_ERROR),
        )
        return

    log_print(f"Found {len(links)} links in {path.name}")

    links_data = [{"url": url, "title": title} for title, url in links]
    queue.create_queue(path.name, links_data)
    queue_data = queue.get_active_queue()
    total, _, _ = queue.get_stats()

    if not queue_data:
        log_print("Queue is empty or invalid", "⚠️")
        return

    for i, item in enumerate(queue_data["items"], 1):
        url = item["url"]
        title = item["title"]
        if item["status"] != "pending":
            continue

        domain = get_domain(url)
        print(f"[{i:3}/{total}] Fetching: {title[:50]}... ({domain})", flush=True)
        start_time = time.time()

        success = False
        error = ProcessingError.UNKNOWN
        if worker_mode == "all":
            success, error = process_article(url, title, model)
        else:
            if not pipeline:
                raise RuntimeError("Pipeline queue is required in worker mode")
            queued = pipeline.enqueue(url, title, source_file=path.name)
            success = queued
            if not queued:
                error = ProcessingError.UNKNOWN

        elapsed = time.time() - start_time
        if success:
            queue.mark_completed(url)
            print(f"[{i:3}/{total}] ✓ {title[:40]} ({elapsed:.1f}s)", flush=True)
        else:
            queue.mark_error(url, error.value)
            print(f"[{i:3}/{total}] ✗ {title[:40]} - {error.value}", flush=True)

    total, completed, errors = queue.get_stats()
    log_print(f"Completed: {completed}/{total} | Errors: {errors}", "✓")
    queue.clear_active()

    config = Config.get()
    if original_path.exists():
        dest = move_to_folder(original_path, config.get_originals_folder())
        if dest:
            log_print(f"Moved to originals: {dest.name}")
    else:
        log_print(f"File already moved: {original_path.name}")


def process_single_file(
    path: Path,
    model: str,
    pipeline: PipelineQueue | None = None,
    worker_mode: str = "all",
):
    name_lower = path.name.lower()
    config = Config.get()

    if name_lower.endswith(".md"):
        non_empty = count_non_empty_lines(path)
        if non_empty == 0:
            log_print(f"Empty file: {path.name}")
            move_to_folder(
                path,
                config.get_errors_folder(),
                get_error_suffix(ProcessingError.EMPTY_CONTENT),
            )
            return

        content = path.read_text(encoding="utf-8", errors="ignore")
        url = extract_url_from_text(content)
        if not url:
            log_print(f"No URL found: {path.name}")
            move_to_folder(
                path,
                config.get_errors_folder(),
                get_error_suffix(ProcessingError.NO_URL_FOUND),
            )
            return

        domain = get_domain(url)
        log_print(f"Processing: {path.name} ({domain})")
        start_time = time.time()

        success = False
        error = ProcessingError.UNKNOWN
        if worker_mode == "all":
            success, error = process_article(url, path.stem, model)
        else:
            if not pipeline:
                raise RuntimeError("Pipeline queue is required in worker mode")
            success = pipeline.enqueue(url, path.stem, source_file=path.name)
            if not success:
                error = ProcessingError.UNKNOWN
            else:
                log_stage("QUEUE", f"enqueued ingest: {path.name}")

        elapsed = time.time() - start_time
        if success:
            log_print(f"✓ {path.name} ({elapsed:.1f}s)")
            move_to_folder(path, config.get_originals_folder())
        else:
            log_print(f"✗ {path.name} - {error.value}")
            move_to_folder(path, config.get_errors_folder(), get_error_suffix(error))
        return

    if name_lower.endswith(".html"):
        log_print(f"HTML file: {path.name}")
        move_to_folder(path, config.get_originals_folder())
        return


def classify_and_process(
    path: Path,
    model: str,
    queue: QueueManager,
    pipeline: PipelineQueue | None = None,
    worker_mode: str = "all",
):
    if path.is_dir():
        return
    if any(x in path.name for x in SKIP_PATTERNS):
        return

    subfolders = ("articles", "processed", "originals", "errors", "Other")
    if any(part in path.parts for part in subfolders):
        return

    name_lower = path.name.lower()
    if name_lower.startswith("tabs") and name_lower.endswith(".html"):
        process_tabs_file(path, model, queue, pipeline=pipeline, worker_mode=worker_mode)
        return

    if path.suffix.lower() not in (".md", ".html"):
        config = Config.get()
        log_print(f"Other file: {path.name}")
        move_to_folder(path, config.get_other_folder())
        return

    process_single_file(path, model, pipeline=pipeline, worker_mode=worker_mode)


def scan_folder(
    folder: Path,
    model: str,
    queue: QueueManager,
    pipeline: PipelineQueue | None = None,
    worker_mode: str = "all",
) -> dict[str, int]:
    stats = {".md": 0, ".html": 0, "tabs": 0, "other": 0}
    subfolders = ("articles", "processed", "originals", "errors", "Other")

    files = [f for f in folder.iterdir() if f.is_file()]
    files += [
        f
        for subfolder in folder.iterdir()
        if subfolder.is_dir() and subfolder.name not in subfolders
        for f in subfolder.rglob("*")
        if f.is_file()
    ]

    for f in files:
        if any(x in f.name for x in SKIP_PATTERNS):
            continue
        if any(part in f.parts for part in subfolders):
            continue
        ext = f.suffix.lower()
        if ext in stats:
            stats[ext] += 1
        elif f.name.lower().startswith("tabs") and ext == ".html":
            stats["tabs"] += 1
        else:
            stats["other"] += 1

    log_print(
        f"Found: {stats['.md']} .md, {stats['.html']} .html, {stats['tabs']} tabs*.html, {stats['other']} other files"
    )

    for p in sorted(files):
        if any(x in p.name for x in SKIP_PATTERNS):
            continue
        if any(part in p.parts for part in subfolders):
            continue
        classify_and_process(
            p, model, queue, pipeline=pipeline, worker_mode=worker_mode
        )

    return stats


class WatchHandler(FileSystemEventHandler):
    def __init__(
        self,
        model: str,
        queue: QueueManager,
        pipeline: PipelineQueue | None = None,
        worker_mode: str = "all",
    ):
        self.model = model
        self.queue = queue
        self.pipeline = pipeline
        self.worker_mode = worker_mode
        self.recently_processed: dict[str, float] = {}

    def _check_file(self, src_path: str):
        try:
            p = Path(src_path)
            if p.is_dir():
                return
            if any(x in p.name for x in SKIP_PATTERNS):
                return

            if src_path in self.recently_processed:
                if time.time() - self.recently_processed[src_path] < DEBOUNCE_TIMEOUT:
                    return

            print(f"[{get_timestamp()}] 📥 New file: {p.name}", flush=True)
            time.sleep(3)

            if p.exists() and p.stat().st_size > 0:
                classify_and_process(
                    p,
                    self.model,
                    self.queue,
                    pipeline=self.pipeline,
                    worker_mode=self.worker_mode,
                )
                self.recently_processed[src_path] = time.time()
            else:
                print(f"[{get_timestamp()}] Disappeared: {p.name}", flush=True)
        except Exception as e:
            log_error(f"Error processing {src_path}: {e}")

    def on_created(self, event):
        if not event.is_directory:
            self._check_file(str(event.src_path))

    def on_modified(self, event):
        if not event.is_directory:
            self._check_file(str(event.src_path))

    def on_moved(self, event):
        if not event.is_directory:
            print(f"[{get_timestamp()}] 📥 Moved file: {Path(event.dest_path).name}", flush=True)
            time.sleep(3)
            p = Path(str(event.dest_path))
            if p.exists() and p.stat().st_size > 0:
                classify_and_process(
                    p,
                    self.model,
                    self.queue,
                    pipeline=self.pipeline,
                    worker_mode=self.worker_mode,
                )
                self.recently_processed[str(event.dest_path)] = time.time()


class QueueHeartbeat:
    def __init__(self, interval_seconds: float):
        self.pipeline = PipelineQueue()
        self.interval_seconds = max(1.0, interval_seconds)
        self._last_snapshot: tuple[int, int, int, int, int] | None = None
        self._was_active = False

    def _snapshot(self) -> tuple[int, int, int, int, int]:
        stats = self.pipeline.get_stats()
        return (
            stats.get("queued_ingest", 0),
            stats.get("queued_llm", 0),
            stats.get("llm_done", 0),
            stats.get("llm_failed", 0),
            stats.get("ingest_failed", 0),
        )

    def run(self):
        log_stage(
            "QUEUE",
            f"heartbeat started (every {self.interval_seconds:.1f}s)",
        )
        while True:
            queued_ingest, queued_llm, llm_done, llm_failed, ingest_failed = self._snapshot()
            snapshot = (queued_ingest, queued_llm, llm_done, llm_failed, ingest_failed)
            has_active_work = queued_ingest > 0 or queued_llm > 0
            just_became_idle = self._was_active and not has_active_work
            should_log = has_active_work or just_became_idle
            if should_log:
                log_stage(
                    "QUEUE",
                    (
                        "heartbeat "
                        f"queued_ingest={queued_ingest} "
                        f"queued_llm={queued_llm} "
                        f"llm_done={llm_done} "
                        f"llm_failed={llm_failed} "
                        f"ingest_failed={ingest_failed}"
                    ),
                )
            self._last_snapshot = snapshot
            self._was_active = has_active_work
            time.sleep(self.interval_seconds)


def watch_folder(
    folder: Path,
    model: str,
    queue: QueueManager,
    pipeline: PipelineQueue | None = None,
    worker_mode: str = "all",
):
    observer = Observer()
    observer.schedule(
        WatchHandler(model, queue, pipeline=pipeline, worker_mode=worker_mode),
        str(folder),
        recursive=False,
    )
    observer.start()
    log_print(f"Watching: {folder}", "👀")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n[{get_timestamp()}] Stopped.", flush=True)
        observer.stop()
    observer.join()


def run_llm_worker(model: str, interval: float = 2.0):
    pipeline = PipelineQueue()
    max_parallel_jobs = Config.get().llm_max_parallel_jobs
    log_stage("LLM", "worker started")
    while True:
        jobs = pipeline.claim_jobs(
            from_status="queued_llm",
            to_status="processing_llm",
            limit=max_parallel_jobs,
        )
        if not jobs:
            time.sleep(interval)
            continue

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max_parallel_jobs
        ) as executor:
            futures = {}
            for job in jobs:
                log_stage("LLM", f"start summarize: #{job['id']} {job['title'][:60]}")
                future = executor.submit(
                    finalize_article,
                    title=job["title"],
                    expanded_url=job["url_expanded"] or job["url_original"],
                    normalized_url=job["url_normalized"] or "",
                    extracted_text=job["extracted_text"] or "",
                    is_yt=bool(job["is_youtube"]),
                    source=get_domain(job["url_expanded"] or job["url_original"]),
                    model=model,
                )
                futures[future] = job
            for future in concurrent.futures.as_completed(futures):
                job = futures[future]
                try:
                    ok, err, out_path = future.result()
                except Exception:
                    ok, err, out_path = False, ProcessingError.UNKNOWN, None
                if ok:
                    pipeline.mark_llm_done(job["id"], str(out_path) if out_path else "")
                    log_stage("LLM", f"done summarize: #{job['id']}")
                else:
                    pipeline.mark_llm_failed(
                        job["id"], err.value, str(out_path) if out_path else None
                    )
                    log_stage("LLM", f"failed summarize: #{job['id']} ({err.value})")


def run_ingest_pipeline_worker(interval: float = 1.0):
    pipeline = PipelineQueue()
    log_stage("QUEUE", "ingest pipeline worker started")
    while True:
        jobs = pipeline.claim_jobs(
            from_status="queued_ingest",
            to_status="processing_ingest",
            limit=20,
        )
        if not jobs:
            time.sleep(interval)
            continue

        for job in jobs:
            log_stage("FILE", f"start ingest: #{job['id']} {job['title'][:60]}")
            ingest, err = ingest_article(job["url_original"], job["title"], force=False)
            if ingest:
                pipeline.mark_ingested(
                    job["id"],
                    expanded_url=ingest["expanded_url"],
                    normalized_url=ingest["normalized_url"],
                    extracted_text=ingest["extracted_text"],
                    is_youtube=ingest["is_youtube"],
                )
                log_stage("QUEUE", f"queued llm: #{job['id']}")
                continue

            if err == ProcessingError.UNKNOWN:
                pipeline.mark_skipped(job["id"], "already_processed")
                log_stage("QUEUE", f"skipped (already processed): #{job['id']}")
            else:
                pipeline.mark_ingest_failed(job["id"], err.value)
                log_stage("FILE", f"ingest failed: #{job['id']} ({err.value})")


def run_ingest_worker(folder: Path, model: str, start_llm_thread: bool = False):
    config = Config.get()
    pipeline = PipelineQueue()
    queue = QueueManager()
    log_stage("FILE", "watch/enqueue worker started")
    heartbeat_thread = threading.Thread(
        target=QueueHeartbeat(config.queue_heartbeat_seconds).run,
        daemon=True,
    )
    heartbeat_thread.start()
    log_print(f"Model: {model} | Folder: {folder}", "⚙️")
    log_print("Scanning folder...", "📋")
    stats = scan_folder(folder, model, queue, pipeline=pipeline, worker_mode="ingest")
    log_print("Summary", "📊")
    log_print(f"  .md files: {stats['.md']}")
    log_print(f"  .html files: {stats['.html']}")
    log_print(f"  tabs files: {stats['tabs']}")
    log_print(f"  other files: {stats['other']}")
    worker_thread = threading.Thread(
        target=run_ingest_pipeline_worker, kwargs={"interval": 0.5}, daemon=True
    )
    worker_thread.start()

    if start_llm_thread:
        llm_thread = threading.Thread(
            target=run_llm_worker, kwargs={"model": model, "interval": 1.0}, daemon=True
        )
        llm_thread.start()
        log_stage("SYSTEM", "all-mode parallel: FILE/QUEUE + LLM workers started")

    watch_folder(folder, model, queue, pipeline=pipeline, worker_mode="ingest")


def main():
    config = Config.get()

    parser = argparse.ArgumentParser(description="Logseq article processor")
    parser.add_argument("path", type=Path, nargs="?", default=config.watch_folder)
    parser.add_argument("--model", default=config.model)
    parser.add_argument("--force", action="store_true", help="Re-process finished files")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--worker",
        choices=("all", "ingest", "llm"),
        default="all",
        help="Run full pipeline, ingest-only, or llm-only worker",
    )
    args = parser.parse_args()

    if args.debug:
        logger.setLevel("DEBUG")

    folder = args.path.resolve()
    log_print("Starting Logseq Processor", "📁")
    log_print(f"Mode: {args.worker} | Model: {args.model} | Folder: {folder}", "⚙️")
    log_print("Config loaded", "✓")
    ensure_folders_exist()
    log_print("Folders created", "✓")

    if args.worker in ("all", "llm") and config.warmup_llm:
        warmup_llm(config.model)

    if args.worker == "llm":
        run_llm_worker(args.model)
        return

    if args.worker == "ingest":
        run_ingest_worker(folder, args.model)
        return

    # In all mode, run both branches in parallel inside one process:
    # - FILE/QUEUE branch: watch + enqueue + ingest extraction
    # - LLM branch: summarize queued_llm jobs
    run_ingest_worker(folder, args.model, start_llm_thread=True)


if __name__ == "__main__":
    main()
