"""
§16 — Benefit Base  (Step 15)

Tracks the death benefit (GMDB) and income benefit (GMWB/i4L) guarantee bases
through projection.

Death benefit (GMDB):
  db_option = 'A' (AV-only): GMDB base = total account value each period.
  db_option = 'B' (return of premium), 'C' (annual ratchet), etc.: not yet
  implemented for this test policy; stubs to AV.

  Confirmed for test policy 842612365: deathbenefittype = 'A', db_option = 'A'.
  GMDB charge rate = expense_charge_per_death_benefit = 0.  No separate GMDB
  charge; under i4L, the GMDB is handled through the i4L GMDB column (BS in
  Calc_SepAcct), which also = 0 when the per-death-benefit charge is 0.

GMWB / i4L income benefit:
  For i4L policies the guaranteed income amount is i4l.current_payment (AP) or
  i4l.monthly_payment (post-AP), NOT a separate GMWB benefit base.
  gmwb_base is set to 4later_current_income_base from the policy (seed value)
  and remains constant (no step-up logic implemented yet — 4Later B4=0).

Output columns (time spine + 4):
    db_base       — death benefit base (= total AV for option A; stub otherwise)
    gmwb_base     — i4L income base (constant seed, no step-up for B4=0)
    gmdb_charge   — GMDB charge amount (0 for test policy)
    gmwb_charge   — GMWB / GLWB charge amount (stub 0; computed in cashflow engine)
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


def build_benefit_base(
    time_axis: pd.DataFrame,
    policy: dict[str, Any],
    config: Any,
) -> pd.DataFrame:
    """
    Build the benefit base spine.

    Parameters
    ----------
    time_axis : output of decrements.time_axis.build_time_axis()
    policy    : output of loaders.policy_loader.load_policy()
    config    : config.Config

    Returns
    -------
    DataFrame (index=projection_period):
        [time-axis pass-through],
        db_base, gmwb_base, gmdb_charge, gmwb_charge
    """
    if time_axis.empty:
        warn("time_axis is empty — returning empty benefit_base DataFrame.",
             source="benefit_base/empty")
        return pd.DataFrame()

    n = len(time_axis)

    # ---- Death benefit -------------------------------------------------------
    db_option = str(policy.get("deathbenefittype") or
                    policy.get("db_option") or "A").strip().upper()

    if db_option != "A":
        warn(
            f"db_option='{db_option}' — only AV-only (option A) is implemented. "
            "db_base will be 0; update once non-AV death benefit logic is built.",
            source="benefit_base/db_option_stub",
        )

    # db_base = AV per period (filled by cashflow engine); seed here = 0
    db_base = np.zeros(n, dtype=float)

    # ---- GMDB charge ---------------------------------------------------------
    gmdb_rate = float(policy.get("expense_charge_per_death_benefit") or 0.0)
    gmdb_charge = np.zeros(n, dtype=float)   # = gmdb_rate × AV / 12 (filled by engine)

    # ---- GMWB / i4L income base ---------------------------------------------
    # Seed from policy; held constant (4Later B4=0, no step-up for test policy)
    gmwb_seed = float(policy.get("4later_current_income_base") or
                      policy.get("gmwb_current_benefit_base") or 0.0)
    gmwb_base   = np.full(n, gmwb_seed, dtype=float)
    gmwb_charge = np.zeros(n, dtype=float)   # stub; computed in cashflow engine

    # ---- Assemble -----------------------------------------------------------
    time_cols = [c for c in _TIME_COLS if c in time_axis.columns]
    df = time_axis[time_cols].copy()
    df["db_base"]     = db_base
    df["gmwb_base"]   = gmwb_base
    df["gmdb_charge"] = gmdb_charge
    df["gmwb_charge"] = gmwb_charge
    df.index.name = "projection_period"
    return df
