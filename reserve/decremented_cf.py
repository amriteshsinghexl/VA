"""
§21 — Decremented Cashflows  (Step 20a)

THE ONLY PLACE where lives weighting is applied to cashflow amounts.
Multiplies each per-unit cashflow column by lives_eop to produce cohort-level
(decremented) cashflow amounts.

  dec_cf[col][t] = undec_cf[col][t] × lives_eop[t]

Layer boundary: cashflows/ → reserve/
  cashflows/ produces per-unit amounts (1 starting life, no decrement)
  reserve/   works with decremented (cohort-weighted) amounts
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from loaders.warnings import warn

_TIME_COLS = {
    "policy_year", "policy_month", "month_in_policy_year",
    "bop_date", "eop_date", "cal_month_end", "attained_age",
    "projection_period",
}


def apply_lives(
    cashflows: pd.DataFrame,
    lives: pd.DataFrame,
) -> pd.DataFrame:
    """
    Return DecCashflowFrame: per-unit cashflow columns × lives_eop.

    Parameters
    ----------
    cashflows : output of cashflows.cashflow_engine.build_cashflows()
                (index = projection_period, columns = per-unit amounts)
    lives     : output of decrements.lives.build_lives()
                must contain column 'lives_eop'

    Returns
    -------
    DataFrame with same shape as cashflows; numeric columns scaled by lives_eop.
    Non-numeric (date, flag) columns are carried through unchanged.
    """
    if cashflows.empty:
        warn("cashflows is empty — returning empty decremented_cf DataFrame.",
             source="decremented_cf/empty")
        return pd.DataFrame()

    if "lives_eop" not in lives.columns:
        warn("lives DataFrame missing 'lives_eop' — returning unscaled cashflows.",
             source="decremented_cf/missing_lives")
        return cashflows.copy()

    idx = cashflows.index
    lives_arr = lives.reindex(idx)["lives_eop"].to_numpy(dtype=float, na_value=np.nan)

    df = cashflows.copy()
    numeric_cols = [
        c for c in df.columns
        if c not in _TIME_COLS and pd.api.types.is_numeric_dtype(df[c])
    ]
    for col in numeric_cols:
        df[col] = df[col].to_numpy(dtype=float) * lives_arr

    # Carry lives_eop through for NAR computation in reserve modules
    df["lives_eop"] = lives_arr

    df.index.name = "projection_period"
    return df
