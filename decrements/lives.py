"""
§10 — Lives Engine

Implements the Calc_Lives decrement spine.

Formula (matches workbook column layout):
  lives_bop[1]   = 1.0                                       (seed — one cohort)
  lives_eop[t]   = lives_bop[t] × (1 − q_mort[t]) × (1 − q_lapse[t])
  lives_bop[t+1] = lives_eop[t]

Inputs:
  mortality : DataFrame from decrements.mortality.build_mortality()
              must contain column 'q_monthly'
  lapse     : DataFrame from decrements.lapse.build_lapse()
              must contain column 'q_lapse_monthly'

NaN propagation:
  Sheets using "[DUMMY placeholder RAND]" string masking (e.g. VM21CA_BaseMortality_Single)
  produce NaN q values and therefore NaN EOP/BOP from period 1 onward.
  VM21PA_BaseMortality_Single uses =RAND()/10 numeric masking instead — openpyxl
  delivers random floats in [0, 0.1] that look like valid rates. For the test
  policy (VM21PA basis) all lives values are therefore finite but meaningless
  until live mortality tables are loaded (D-015).

Note on the stub test comment 'lives_eop[1] = 0.70 (30% lapse shock)':
  This was a provisional placeholder written before the lapse and mortality
  engines were implemented.  No shock-lapse table exists in
  Assumptions_Extracted.xlsx.  The actual EOP[1] value cannot be verified
  because the RAND()/10 masking in VM21PA_BaseMortality_Single produces a
  different random q each Excel recalculation.  The test is kept skipped
  pending live-workbook verification.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from loaders.warnings import warn


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_lives(
    mortality: pd.DataFrame,
    lapse: pd.DataFrame,
    config: Any,
) -> pd.DataFrame:
    """
    Build the Calc_Lives decrement spine for one policy.

    Parameters
    ----------
    mortality : output of decrements.mortality.build_mortality()
    lapse     : output of decrements.lapse.build_lapse()
    config    : config.Config instance (reserved for future use)

    Returns
    -------
    DataFrame (index=projection_period) with columns:
        policy_year, policy_month, month_in_policy_year,
        bop_date, eop_date, cal_month_end, attained_age,
        q_mort_monthly, q_lapse_monthly,
        lives_bop, lives_eop
    """
    if mortality.empty:
        warn("mortality DataFrame is empty — returning empty lives DataFrame.",
             source="lives/empty_mortality")
        return pd.DataFrame()

    if lapse.empty:
        warn("lapse DataFrame is empty — returning empty lives DataFrame.",
             source="lives/empty_lapse")
        return pd.DataFrame()

    # Align indices — both are indexed by projection_period
    idx = mortality.index
    if not idx.equals(lapse.index):
        warn(
            "mortality and lapse indices do not match — aligning on mortality index.",
            source="lives/index_mismatch",
        )
        lapse = lapse.reindex(idx)

    q_mort_arr   = mortality["q_monthly"].to_numpy(dtype=float, na_value=np.nan)
    q_lapse_arr  = lapse["q_lapse_monthly"].to_numpy(dtype=float, na_value=np.nan)

    bop_arr, eop_arr = _lives_recurrence(q_mort_arr, q_lapse_arr)

    # Pass-through time-axis columns from mortality
    _TIME_COLS = [
        "policy_year", "policy_month", "month_in_policy_year",
        "bop_date", "eop_date", "cal_month_end", "attained_age",
    ]
    time_cols = [c for c in _TIME_COLS if c in mortality.columns]
    df = mortality[time_cols].copy()
    df["q_mort_monthly"]  = q_mort_arr
    df["q_lapse_monthly"] = q_lapse_arr
    df["lives_bop"]       = bop_arr
    df["lives_eop"]       = eop_arr
    df.index.name = "projection_period"
    return df


# ---------------------------------------------------------------------------
# Core recurrence (exposed for unit testing)
# ---------------------------------------------------------------------------

def _lives_recurrence(
    q_mort: np.ndarray,
    q_lapse: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute BOP and EOP lives arrays from decrement rate arrays.

    lives_bop[0] = 1.0 (seed)
    lives_eop[t] = lives_bop[t] × (1 − q_mort[t]) × (1 − q_lapse[t])
    lives_bop[t+1] = lives_eop[t]

    NaN in either decrement propagates to EOP and forward to subsequent BOPs.

    Parameters
    ----------
    q_mort  : 1-D array of monthly mortality rates, length N
    q_lapse : 1-D array of monthly lapse rates, length N

    Returns
    -------
    (bop_arr, eop_arr) : two float64 arrays of length N
    """
    n = len(q_mort)
    bop_arr = np.empty(n, dtype=float)
    eop_arr = np.empty(n, dtype=float)

    bop_arr[0] = 1.0
    for t in range(n):
        bop = bop_arr[t]
        qm  = q_mort[t]
        ql  = q_lapse[t]

        if math.isnan(bop) or math.isnan(qm) or math.isnan(ql):
            eop = np.nan
        else:
            eop = bop * (1.0 - qm) * (1.0 - ql)

        eop_arr[t] = eop
        if t + 1 < n:
            bop_arr[t + 1] = eop  # NaN propagates naturally

    return bop_arr, eop_arr
