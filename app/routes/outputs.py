"""
Output file browsing routes.

GET  /api/v1/outputs               â€” list all Excel files in abc_corp_va/results/
GET  /api/v1/outputs/download/{f}  â€” download a result Excel file
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import settings
from app.schemas.model import AvailableFile, AvailableFilesResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["outputs"])

_RESULTS_DIR = Path(settings.base_dir) / "abc_corp_va" / "results"


@router.get("/outputs", response_model=AvailableFilesResponse)
def list_outputs():
    """List all Excel result files produced by previous VA runs."""
    if not _RESULTS_DIR.exists():
        return AvailableFilesResponse(files=[])

    files = [
        AvailableFile(
            filename=f.name,
            size_bytes=f.stat().st_size,
            download_url=f"/api/v1/outputs/download/{f.name}",
        )
        for f in sorted(_RESULTS_DIR.glob("*.xlsx"))
        if f.is_file()
    ]
    return AvailableFilesResponse(files=files)


@router.get("/outputs/download/{filename}")
def download_output(filename: str):
    """Download a result Excel workbook by filename."""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    file_path = _RESULTS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found")
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
