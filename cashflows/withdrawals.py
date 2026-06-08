"""
§18 — Withdrawals  (Step 17)

Computes the guaranteed income withdrawal amount per projection period for
i4L policies.

For i4L policies:
  monthly_withdrawal[t] = i4l.monthly_payment[t]    (= i4l.current_payment / 12)

  Within AP (O > 0): payments are the "current payment" from the annuity-
  pricing formula — (AV − i4L_charge) / (V + W) / 12.
  Post-AP (O ≤ 0): payments continue at the ratcheted floor AN / 12.

The monthly_payment column in the i4l engine is currently stubbed at 0 (pending
cashflow engine integration that provides AV).  This module passes through the
i4l.monthly_payment column so that the cashflow engine has a single place to
read withdrawals.

Non-i4L policies: withdrawal = 0 (no GMWB rider for test policy outside i4L).

Output: DataFrame (480 × 9) with time spine + withdrawal columns.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Any

from loaders.warnings import warn

_TIME_COLS = [
    "policy_year", "policy_month", "month_in_policy_year",
    "bop_date", "eop_date", "cal_month_end", "attained_age",
]


def build_withdrawals(
    time_axis: pd.DataFrame,
    policy: dict[str, Any],
    i4l: pd.DataFrame,
    config: Any,
) -> pd.DataFrame:
    """
    Build the per-period withdrawal amounts.

    Parameters
    ----------
    time_axis : output of decrements.time_axis.build_time_axis()
    policy    : output of loaders.policy_loader.load_policy()
    i4l       : output of cashflows.i4l.build_i4l()
    config    : config.Config

    Returns
    -------
    DataFrame (index=projection_period) with columns:
        [time-axis pass-through],
        monthly_withdrawal   — guaranteed monthly income payment
        annual_withdrawal    — × 12
        is_in_ap             — True while AP remaining > 0 (within access period)
    """
    if time_axis.empty:
        warn("time_axis is empty — returning empty withdrawals DataFrame.",
             source="withdrawals/empty")
        return pd.DataFrame()

    indicator = str(policy.get("i4l_indicator") or "").strip()
    n = len(time_axis)

    time_cols = [c for c in _TIME_COLS if c in time_axis.columns]
    df = time_axis[time_cols].copy()

    if indicator != "i4L" or i4l.empty:
        df["monthly_withdrawal"] = 0.0
        df["annual_withdrawal"]  = 0.0
        df["is_in_ap"]           = False
        df.index.name = "projection_period"
        return df

    # Pass through i4l monthly payment (= 0 stub until cashflow engine fills it)
    idx = time_axis.index
    monthly = i4l.reindex(idx)["monthly_payment"].to_numpy(dtype=float, na_value=0.0)
    o_rem   = i4l.reindex(idx)["o_ap_remaining"].to_numpy(dtype=float, na_value=0.0)

    df["monthly_withdrawal"] = monthly
    df["annual_withdrawal"]  = monthly * 12.0
    df["is_in_ap"]           = o_rem > 0

    df.index.name = "projection_period"
    return df
