"""
Standalone FastAPI service for VA policy input data.

Reads Input_PolicyDataRaw.xlsx (row 1 = field names, row 2 = policy data).

Usage:
    python -m uvicorn policy_data_api:app --port 8012 --reload
    -- or via run_all.py --

Endpoints:
    GET  /              API root + file info
    GET  /policy        The single policy record as a dict
    GET  /fields        All field names
    GET  /fields/{name} Value of a specific field
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException

DATA_FILE = (
    Path(__file__).resolve().parent.parent / "abc_corp_va" / "data" / "Input_PolicyDataRaw.xlsx"
)

app = FastAPI(
    title="VA Policy Data API",
    description="REST API for the Abc_corp VA input policy workbook",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_policy() -> Dict[str, Any]:
    """Load the single policy row from Input_PolicyDataRaw.xlsx."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(str(DATA_FILE), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        wb.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not read policy file: {exc}")

    if len(rows) < 2:
        raise HTTPException(status_code=404, detail="Policy file has fewer than 2 rows")

    fields = [str(h) if h is not None else f"col_{i}" for i, h in enumerate(rows[0])]
    values = rows[1]
    return dict(zip(fields, values))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    exists = DATA_FILE.exists()
    return {
        "message": "VA Policy Data API",
        "data_file": str(DATA_FILE),
        "file_exists": exists,
        "size_bytes": DATA_FILE.stat().st_size if exists else None,
    }


@app.get("/policy")
def get_policy():
    """Return all fields of the single policy record."""
    return {"data": _load_policy()}


@app.get("/fields")
def list_fields():
    """Return all field names in the policy workbook."""
    policy = _load_policy()
    return {"field_count": len(policy), "fields": list(policy.keys())}


@app.get("/fields/{name}")
def get_field(name: str):
    """Return the value of a specific field."""
    policy = _load_policy()
    if name not in policy:
        available = list(policy.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Field '{name}' not found. Available fields: {available[:20]}{'...' if len(available) > 20 else ''}",
        )
    return {"field": name, "value": policy[name]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("policy_data_api:app", host="0.0.0.0", port=8012, reload=True)
