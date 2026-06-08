"""
Model execution routes.

POST /api/v1/run-model          — submit a VA job (returns job_id immediately)
GET  /api/v1/job-status/{id}   — poll status + streamed log lines
GET  /api/v1/results/{id}      — get result file list (completed jobs only)
GET  /api/v1/jobs              — list all job IDs
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException

from app.schemas.model import (
    JobResultResponse,
    JobStatus,
    JobStatusResponse,
    RunModelRequest,
)
from app.services.job_store import job_store
from app.services.model_service import submit_job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["model"])


@router.post("/run-model", status_code=202)
def run_model(request: RunModelRequest):
    """Submit a VA model run.  Returns *job_id* immediately; poll job-status for progress."""
    job_id = str(uuid.uuid4())
    submit_job(job_id, request)
    logger.info(
        "Submitted VA job %s  basis=%s  method=%s  months=%d",
        job_id, request.reserve_basis.value, request.reserve_method.value, request.months,
    )
    return {"job_id": job_id, "status": "pending"}


@router.get("/job-status/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str):
    """Return current status and all captured log lines for a job."""
    rec = job_store.get(job_id)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    elapsed: Optional[float] = None
    if rec.started_at:
        end = rec.completed_at or datetime.now(timezone.utc)
        elapsed = (end - rec.started_at).total_seconds()

    return JobStatusResponse(
        job_id=rec.job_id,
        status=rec.status,
        created_at=rec.created_at,
        started_at=rec.started_at,
        completed_at=rec.completed_at,
        elapsed_seconds=elapsed,
        progress=rec.progress,
        log_lines=list(rec.log_lines),
        error=rec.error,
    )


@router.get("/results/{job_id}", response_model=JobResultResponse)
def get_results(job_id: str):
    """Return output file metadata for a completed job."""
    rec = job_store.get(job_id)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    if rec.status != JobStatus.completed:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed (current status: {rec.status.value})",
        )

    elapsed: Optional[float] = None
    if rec.started_at and rec.completed_at:
        elapsed = (rec.completed_at - rec.started_at).total_seconds()

    return JobResultResponse(
        job_id=rec.job_id,
        status=rec.status,
        output_file=rec.output_file,
        output_files=rec.output_files,
        elapsed_seconds=elapsed,
    )


@router.get("/jobs")
def list_jobs():
    """List all job IDs in the current session."""
    return {"jobs": job_store.list_ids()}
