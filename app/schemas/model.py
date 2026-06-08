from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ReserveBasis(str, Enum):
    VM21PA = "VM21PA"
    VM21CA = "VM21CA"
    NYREG213 = "NYREG213"
    GAAPDAC = "GAAPDAC"
    CAPITAL = "CAPITAL"


class ReserveMethod(str, Enum):
    StdScn = "StdScn"
    CARVM = "CARVM"
    OptionValueFloor = "OptionValueFloor"


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class RunModelRequest(BaseModel):
    reserve_basis: ReserveBasis = Field(
        default=ReserveBasis.VM21PA,
        description="Valuation reserve basis.",
    )
    reserve_method: ReserveMethod = Field(
        default=ReserveMethod.StdScn,
        description="Reserve calculation method.",
    )
    policy_id: Optional[str] = Field(
        default=None,
        description="Policy number to load. Defaults to the first data row.",
    )
    months: int = Field(
        default=480,
        ge=1,
        le=1080,
        description="Projection horizon in months.",
    )
    output_dir: Optional[str] = Field(
        default=None,
        description="Output directory. Defaults to abc_corp_va/results/.",
    )


# ---------------------------------------------------------------------------
# Job tracking
# ---------------------------------------------------------------------------

class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    elapsed_seconds: Optional[float] = None
    progress: Optional[str] = None
    log_lines: List[str] = []
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

class OutputFile(BaseModel):
    filename: str
    size_bytes: int
    download_url: str


class JobResultResponse(BaseModel):
    job_id: str
    status: JobStatus
    output_file: Optional[str] = None
    output_files: List[OutputFile] = []
    elapsed_seconds: Optional[float] = None


class AvailableFile(BaseModel):
    filename: str
    size_bytes: int
    download_url: str


class AvailableFilesResponse(BaseModel):
    files: List[AvailableFile]
