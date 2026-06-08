"""
VA model execution service.

Spawns abc_corp_va/run.py in a background thread so the FastAPI event loop
stays responsive.  Captures stdout line-by-line into the job store so the
Express UI can poll progress via GET /api/v1/job-status/{job_id}.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.schemas.model import JobStatus, OutputFile, RunModelRequest
from app.services.job_store import job_store

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(settings.base_dir)
_ABC_CORP_DIR = _PROJECT_ROOT / "abc_corp_va"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def submit_job(job_id: str, request: RunModelRequest) -> None:
    """Create a job record and launch it in a daemon thread."""
    job_store.create(job_id)
    t = threading.Thread(
        target=_execute,
        args=(job_id, request),
        daemon=True,
        name=f"va-job-{job_id[:8]}",
    )
    t.start()


# ---------------------------------------------------------------------------
# Internal execution (runs in background thread)
# ---------------------------------------------------------------------------

def _execute(job_id: str, request: RunModelRequest) -> None:
    logger.info("VA job %s starting", job_id)
    job_store.mark_running(job_id, "Starting abc_corp_va/run.py")

    wall_start = time.perf_counter()

    cmd = [
        settings.python_exec,
        "run.py",
        "--reserve-basis", request.reserve_basis.value,
        "--reserve-method", request.reserve_method.value,
        "--months", str(request.months),
    ]
    if request.policy_id:
        cmd += ["--policy-id", request.policy_id]
    if request.output_dir:
        cmd += ["--output-dir", request.output_dir]

    logger.info("VA job %s cmd: %s", job_id, " ".join(cmd))

    output_file: Optional[str] = None

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(_ABC_CORP_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        for raw_line in proc.stdout:
            line = raw_line.rstrip("\n\r")
            job_store.append_line(job_id, line)

            # Parse output path from the completion banner line:
            # "  Output:   C:\projects\VA\abc_corp_va\results\abc_corp_va_*.xlsx"
            if "Output:" in line and ".xlsx" in line:
                parts = line.split("Output:", 1)
                if len(parts) > 1:
                    output_file = parts[1].strip()

            # Update progress from step markers "[N/15] Label ..."
            if line.lstrip().startswith("[") and "/15]" in line:
                job_store.update_progress(job_id, line.strip())

        proc.wait()
        elapsed = time.perf_counter() - wall_start

        if proc.returncode == 0:
            output_files = _enumerate_output_files(output_file, job_id)
            job_store.mark_completed(
                job_id,
                output_file=output_file,
                output_files=output_files,
                total_elapsed=elapsed,
            )
            logger.info(
                "VA job %s completed in %.2fs â€” output: %s",
                job_id, elapsed, output_file,
            )
        else:
            job_store.mark_failed(
                job_id,
                f"Process exited with code {proc.returncode}",
            )
            logger.error(
                "VA job %s failed after %.2fs (exit code %d)",
                job_id, elapsed, proc.returncode,
            )

    except Exception as exc:
        elapsed = time.perf_counter() - wall_start
        logger.exception("VA job %s raised an exception after %.2fs", job_id, elapsed)
        job_store.append_line(job_id, f"[error] {exc}")
        job_store.mark_failed(job_id, str(exc))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _enumerate_output_files(
    output_file: Optional[str], job_id: str
) -> list[OutputFile]:
    if not output_file:
        return []
    p = Path(output_file)
    if not p.exists():
        return []
    return [
        OutputFile(
            filename=p.name,
            size_bytes=p.stat().st_size,
            download_url=f"/api/v1/outputs/download/{p.name}",
        )
    ]
