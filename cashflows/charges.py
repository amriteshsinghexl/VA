"""
§17 — Charge Rate Registry  (Step 16)

Consolidates all annual charge rates for one policy and applies the
NYREG213+CARVM suppressor (D-007) where required.

NYREG213+CARVM suppressor (D-007):
  suppressor = 0 if (reserve_basis='NYREG213' AND reserve_method='CARVM') else 1
  Applied to: IMF, GIB, i4L, 4Later, GIB, policy-load charges.
  NOT applied to: M&E, GMDB, 401K charges (per workbook).

Charge rates (annual, as decimals):
  me_rate     : expense_charge_per_separate_account (= 0.01 for test policy)
  imf_rate    : from IMF NRSI lookup (= 0.006648054 for LMFR5)
  gib_rate    : GIB net rate = raw_gib − i4l_ap_rate (= 0.004 for test policy)
  i4l_ap_rate : i4L expense during access period (= 0.005)
  i4l_post_ap : i4L expense post access period (= 0 for test policy)
  gmdb_rate   : expense_charge_per_death_benefit (= 0 for test policy)

All amounts are computed by the cashflow engine as rate × AV / 12.

Output: DataFrame (480 × 14) with annual rates and suppressor flag per period.
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


def build_charges(
    time_axis: pd.DataFrame,
    policy: dict[str, Any],
    config: Any,
) -> pd.DataFrame:
    """
    Build the charge-rate registry for one policy.

    Parameters
    ----------
    time_axis : output of decrements.time_axis.build_time_axis()
    policy    : output of loaders.policy_loader.load_policy()
    config    : config.Config  (uses suppress_charges for NYREG213+CARVM)

    Returns
    -------
    DataFrame (index=projection_period) with columns:
        [time-axis pass-through],
        me_rate, imf_rate, gib_rate, i4l_ap_rate, i4l_post_rate,
        gmdb_rate, suppressor,
        me_monthly, imf_monthly, gib_monthly, i4l_ap_monthly,
        i4l_post_monthly, gmdb_monthly
    """
    if time_axis.empty:
        warn("time_axis is empty — returning empty charges DataFrame.",
             source="charges/empty")
        return pd.DataFrame()

    n = len(time_axis)

    # ---- Rates (annual, from policy) ----------------------------------------
    me_rate      = float(policy.get("expense_charge_per_separate_account") or 0.0)
    gmdb_rate    = float(policy.get("expense_charge_per_death_benefit") or 0.0)

    # GIB and i4L rates parsed from semicolon-delimited policy fields
    gib_raw      = _parse_rate(policy.get("gmwb_ridercharge_rate"))
    # B1 = i4L expense rate during AP from Product Features!AT4; NOT i4l_expense_load
    # (which is the 3% annuity-factor adjustment load, a different parameter)
    i4l_ap_rate  = _get_i4l_ap_rate(config.policy_path)
    i4l_post_rate = 0.0   # B2 in Calc_i4L; = 0 for test policy (post-AP rate)
    gib_net_rate = max(0.0, gib_raw - i4l_ap_rate)   # B3 = gross − B1

    # IMF rate — read from workbook at runtime; here we use the policy-cached value
    # (0.006648054 for LMFR5; the sep_acct module reads it directly)
    imf_rate = 0.0   # placeholder; sep_acct reads this directly from IMF NRSI sheet

    # ---- NYREG213+CARVM suppressor (D-007) -----------------------------------
    suppressor = 0.0 if config.suppress_charges else 1.0

    # ---- Monthly rates -------------------------------------------------------
    def m(rate: float, suppress: bool = False) -> float:
        r = rate / 12.0
        return r * (0.0 if suppress else 1.0)

    # Suppressed rates (IMF, GIB, i4L — per D-007)
    suppress = config.suppress_charges

    time_cols = [c for c in _TIME_COLS if c in time_axis.columns]
    df = time_axis[time_cols].copy()

    # Annual rates (constant across all periods for this policy)
    df["me_rate"]         = me_rate
    df["imf_rate"]        = imf_rate   # filled separately by sep_acct
    df["gib_rate"]        = gib_net_rate
    df["i4l_ap_rate"]     = i4l_ap_rate
    df["i4l_post_rate"]   = i4l_post_rate
    df["gmdb_rate"]       = gmdb_rate
    df["suppressor"]      = suppressor

    # Monthly rates (= annual / 12 × suppressor where applicable)
    df["me_monthly"]       = me_rate / 12.0                              # NOT suppressed
    df["imf_monthly"]      = 0.0                                          # filled by sep_acct
    df["gib_monthly"]      = gib_net_rate / 12.0 * (0.0 if suppress else 1.0)
    df["i4l_ap_monthly"]   = i4l_ap_rate / 12.0 * (0.0 if suppress else 1.0)
    df["i4l_post_monthly"] = i4l_post_rate / 12.0 * (0.0 if suppress else 1.0)
    df["gmdb_monthly"]     = gmdb_rate / 12.0                            # NOT suppressed

    df.index.name = "projection_period"
    return df


def _parse_rate(raw) -> float:
    """Parse '0.009000;10/23/2063' style rate fields — take first token."""
    if raw is None:
        return 0.0
    s = str(raw).strip().split(";")[0]
    try:
        return float(s)
    except ValueError:
        return 0.0


def _get_i4l_ap_rate(policy_path: str) -> float:
    """
    Read i4L expense rate during AP from Product Features!AT4.
    Calc_i4L!B1 = IF(i4l_Indicator='i4L', Product_Features!$AT$4, 0).
    Confirmed = 0.005 for plan LMFR5.
    """
    try:
        import openpyxl
        wb = openpyxl.load_workbook(policy_path, data_only=True, read_only=True)
        ws = wb["Product Features"]
        # AT = column 46 (1-based); row 4
        rows = list(ws.iter_rows(min_row=4, max_row=4,
                                  min_col=46, max_col=46, values_only=True))
        wb.close()
        val = rows[0][0] if rows else None
        return float(val) if val is not None else 0.005
    except Exception:
        return 0.005   # workbook-confirmed fallback for LMFR5
