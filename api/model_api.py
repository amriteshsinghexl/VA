"""
Standalone FastAPI service for running the Abc_corp VA model.

Usage:
    python -m uvicorn model_api:app --port 8011 --reload
    -- or via run_all.py --

Endpoints:
    POST /run          Submit a VA run job â†’ returns job_id
    GET  /job/{id}     Poll status + captured log lines
    GET  /jobs         List all job IDs
"""

from __future__ import annotations

import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

ABC_CORP_DIR = Path(__file__).resolve().parent.parent / "abc_corp_va"
PYTHON = sys.executable

app = FastAPI(
    title="VA Model API",
    description="Standalone service for submitting and monitoring Abc_corp VA model runs",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class RunRequest(BaseModel):
    reserve_basis: str = "VM21PA"    # VM21PA | VM21CA | NYREG213 | GAAPDAC | CAPITAL
    reserve_method: str = "StdScn"  # StdScn | CARVM | OptionValueFloor
    policy_id: Optional[str] = None
    months: int = 480
    output_dir: Optional[str] = None


# ---------------------------------------------------------------------------
# In-memory job store
# ---------------------------------------------------------------------------

@dataclass
class Job:
    job_id: str
    status: str = "pending"           # pending | running | completed | failed
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    log_lines: List[str] = field(default_factory=list)
    output_file: Optional[str] = None
    error: Optional[str] = None


_jobs: Dict[str, Job] = {}
_lock = threading.Lock()


def _create_job(job_id: str) -> Job:
    j = Job(job_id=job_id)
    with _lock:
        _jobs[job_id] = j
    return j


def _get_job(job_id: str) -> Optional[Job]:
    with _lock:
        return _jobs.get(job_id)


# ---------------------------------------------------------------------------
# Background execution
# ---------------------------------------------------------------------------

def _run(job_id: str, request: RunRequest) -> None:
    j = _get_job(job_id)
    with _lock:
        j.status = "running"
        j.started_at = datetime.now(timezone.utc)

    cmd = [
        PYTHON, "run.py",
        "--reserve-basis", request.reserve_basis,
        "--reserve-method", request.reserve_method,
        "--months", str(request.months),
    ]
    if request.policy_id:
        cmd += ["--policy-id", request.policy_id]
    if request.output_dir:
        cmd += ["--output-dir", request.output_dir]

    output_file: Optional[str] = None

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(ABC_CORP_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        for raw in proc.stdout:
            line = raw.rstrip("\n\r")
            with _lock:
                j.log_lines.append(line)
            if "Output:" in line and ".xlsx" in line:
                output_file = line.split("Output:", 1)[1].strip()

        proc.wait()

        with _lock:
            j.completed_at = datetime.now(timezone.utc)
            j.output_file = output_file
            j.status = "completed" if proc.returncode == 0 else "failed"
            if proc.returncode != 0:
                j.error = f"Process exited with code {proc.returncode}"

    except Exception as exc:
        with _lock:
            j.log_lines.append(f"[error] {exc}")
            j.status = "failed"
            j.error = str(exc)
            j.completed_at = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {"message": "VA Model API", "abc_corp_dir": str(ABC_CORP_DIR)}


@app.post("/run", status_code=202)
def run_model(request: RunRequest):
    """Submit a VA model run. Returns immediately with job_id."""
    job_id = str(uuid.uuid4())
    _create_job(job_id)
    t = threading.Thread(target=_run, args=(job_id, request), daemon=True)
    t.start()
    return {"job_id": job_id, "status": "pending"}


@app.get("/job/{job_id}")
def get_job(job_id: str):
    """Poll status and captured log lines."""
    j = _get_job(job_id)
    if not j:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    elapsed = None
    if j.started_at:
        end = j.completed_at or datetime.now(timezone.utc)
        elapsed = (end - j.started_at).total_seconds()
    return {
        "job_id": j.job_id,
        "status": j.status,
        "created_at": j.created_at.isoformat(),
        "started_at": j.started_at.isoformat() if j.started_at else None,
        "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        "elapsed_seconds": elapsed,
        "output_file": j.output_file,
        "log_lines": list(j.log_lines),
        "error": j.error,
    }


@app.get("/jobs")
def list_jobs():
    with _lock:
        return {"jobs": list(_jobs.keys())}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("model_api:app", host="0.0.0.0", port=8011, reload=True)
