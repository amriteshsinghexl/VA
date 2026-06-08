"""
Output Builder  (STUB)

Writes abc_corp_va_output.xlsx with five sheets:
  1. Decrements       â€” DecrementsFrame
  2. Undec_Cashflows  â€” UndecCashflowFrame
  3. Dec_Cashflows    â€” DecCashflowFrame
  4. Reserve_Summary  â€” aggregated reserve results
  5. Warnings         â€” all ModelWarning entries captured during the run
"""
from __future__ import annotations

import pandas as pd
from pathlib import Path


def write_output(
    decrements: pd.DataFrame,
    undec_cf: pd.DataFrame,
    dec_cf: pd.DataFrame,
    reserve_summary: pd.DataFrame,
    output_dir: str,
    filename: str = "abc_corp_va_output.xlsx",
) -> Path:
    raise NotImplementedError("DUMMY â€” output_builder not yet implemented")
