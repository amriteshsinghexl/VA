"""
In-memory job store for VA model execution tracking.

Thread-safe via a single lock.  For multi-worker production deployments,
replace with a Redis or database-backed store.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.schemas.model import JobStatus, OutputFile


class JobRecord:
    __slots__ = (
        "job_id", "status", "created_at", "started_at", "completed_at",
        "progress", "error", "output_file", "output_files",
        "total_elapsed_seconds", "log_lines",
    )

    def __init__(self, job_id: str) -> None:
        self.job_id: str = job_id
        self.status: JobStatus = JobStatus.pending
        self.created_at: datetime = datetime.now(timezone.utc)
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.progress: Optional[str] = None
        self.error: Optional[str] = None
        self.output_file: Optional[str] = None
        self.output_files: List[OutputFile] = []
        self.total_elapsed_seconds: Optional[float] = None
        self.log_lines: List[str] = []


class JobStore:
    def __init__(self) -> None:
        self._jobs: Dict[str, JobRecord] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Mutations (called from background thread)
    # ------------------------------------------------------------------

    def create(self, job_id: str) -> JobRecord:
        record = JobRecord(job_id)
        with self._lock:
            self._jobs[job_id] = record
        return record

    def mark_running(self, job_id: str, progress: Optional[str] = None) -> None:
        with self._lock:
            rec = self._jobs[job_id]
            rec.status = JobStatus.running
            rec.started_at = datetime.now(timezone.utc)
            rec.progress = progress

    def update_progress(self, job_id: str, message: str) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].progress = message

    def append_line(self, job_id: str, line: str) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].log_lines.append(line)

    def mark_completed(
        self,
        job_id: str,
        output_file: Optional[str] = None,
        output_files: Optional[List[OutputFile]] = None,
        total_elapsed: Optional[float] = None,
    ) -> None:
        with self._lock:
            rec = self._jobs[job_id]
            rec.status = JobStatus.completed
            rec.completed_at = datetime.now(timezone.utc)
            rec.output_file = output_file
            rec.output_files = output_files or []
            if total_elapsed is not None:
                rec.total_elapsed_seconds = total_elapsed
            elif rec.started_at:
                rec.total_elapsed_seconds = (
                    rec.completed_at - rec.started_at
                ).total_seconds()

    def mark_failed(self, job_id: str, error: str) -> None:
        with self._lock:
            rec = self._jobs[job_id]
            rec.status = JobStatus.failed
            rec.completed_at = datetime.now(timezone.utc)
            rec.error = error

    # ------------------------------------------------------------------
    # Reads (called from request handlers)
    # ------------------------------------------------------------------

    def get(self, job_id: str) -> Optional[JobRecord]:
        with self._lock:
            return self._jobs.get(job_id)

    def list_ids(self) -> List[str]:
        with self._lock:
            return list(self._jobs.keys())


job_store = JobStore()
