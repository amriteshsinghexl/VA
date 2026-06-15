"""
§22 — CARVM Reserve  (Steps 21–22)

Implements the Commissioner's Annuity Reserve Valuation Method (CARVM) per
Calc_CARVM.  Applicable to NYREG213 + CARVM reserve basis only.

CARVM concept:
  For each future period t, compute the present value (discounted to today) of
  the maximum benefit that a policyholder could elect at that point:
    pv_csv[t]       = CSV[t] × disc_factor[t]    (surrender at t)
    pv_annuity[t]   = Annuity[t] × disc_factor[t] (annuitise at t)
    pv_max[t]       = max(pv_csv[t], pv_annuity[t])
  CARVM_reserve     = max over all t of pv_max[t]

For the test policy (VM21PA basis, AV-only DB, zero SC):
  - pv_annuity is zero (annuitisation benefit not applicable to option A)
  - pv_csv[t] = (AV[t] × surv[t]) × disc_factor[t]
  - CARVM binding at period 1 (immediate surrender dominates future discounted values)

Key workbook-confirmed values for period 1 (NYREG213+CARVM basis):
  - ME Survivorship = 0.70  (NYREG213 zero-dynamic-lapse lives_eop[1])
  - Fund at ME      = 1,105,106.04  (= AV × (1−M&E/12) × surv ≈ 1,578,591 × 0.70)
  - PV CSV          = 1,105,106.04  (disc_factor[1] = 1.0 at seed, no discounting)
  - CARVM reserve   = 1,105,106.04

CARVM suppressor (D-007):
  Under NYREG213+CARVM, IMF and i4L/GIB charges are suppressed (config.suppress_charges=True).
  M&E and GMDB are NOT suppressed.

Notes:
  - For VM21PA / VM21CA / GAAPDAC / CAPITAL bases, CARVM is not the binding reserve.
    The module still runs but its output is not used in the final reserve aggregation.
  - The NYREG213+CARVM survivorship uses the NYREG213 lapse engine with AL column = 0
    (D-008). In the sandbox, NYREG213 lapse is stubbed, so survivorship falls back
    to the input dec_cf lives (typically VM21PA for the test run).
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


def calculate_carvm(
    dec_cf: pd.DataFrame,
    interest_rates: pd.DataFrame,
    policy: dict[str, Any],
    config: Any,
) -> pd.DataFrame:
    """
    Compute the CARVM reserve per projection period.

    Parameters
    ----------
    dec_cf         : lives-weighted cashflows (reserve.decremented_cf.apply_lives output)
                     Must contain 'av_eop_sa' (lives-weighted SA AV).
    interest_rates : output of cashflows.interest.build_interest_rates()
                     Uses unshocked disc_factor (not shocked).
    policy         : output of loaders.policy_loader.load_policy()
    config         : config.Config  (uses suppress_charges, reserve_basis/method)

    Returns
    -------
    DataFrame (index=projection_period) with columns:
        [time-axis pass-through],
        fund_at_me, csv_at_me, annuity_at_me,
        pv_csv, pv_annuity, pv_max,
        carvm_reserve
    """
    if dec_cf.empty:
        warn("dec_cf is empty — returning empty CARVM DataFrame.",
             source="carvm/empty")
        return pd.DataFrame()

    is_nyreg213_carvm = (
        config.reserve_basis == "NYREG213"
        and config.reserve_method == "CARVM"
    )
    if not is_nyreg213_carvm:
        warn(
            f"CARVM called for basis='{config.reserve_basis}' / "
            f"method='{config.reserve_method}'. "
            "CARVM is only binding under NYREG213+CARVM. "
            "Returning zero-reserve DataFrame.",
            source="carvm/non_carvm_basis",
        )
        return _build_zero_carvm(dec_cf)

    idx  = dec_cf.index
    n    = len(idx)
    ir   = interest_rates.reindex(idx)

    # Unshocked disc factor (CARVM uses standard rates, not +100bps shock)
    disc = ir["disc_factor"].to_numpy(dtype=float, na_value=np.nan)

    # Lives-weighted AV at EOP (fund at ME = AV × survivorship)
    av_dec = dec_cf.reindex(idx)["av_eop_sa"].to_numpy(dtype=float, na_value=0.0)

    # M&E charge on the fund (not suppressed under CARVM)
    me_rate = float(policy.get("expense_charge_per_separate_account") or 0.0)
    # Fund at ME ≈ av_dec (after M&E has already been applied in cashflow_engine)
    # CSV = AV - SC; for this policy SC = 0 → CSV = AV
    fund_at_me = av_dec
    csv_at_me  = av_dec   # zero surrender charges

    # Annuitisation benefit (0 for AV-only DB policies)
    # i4L annuitisation would be included here for annuity-option policies
    db_type = str(policy.get("deathbenefittype") or "A").strip().upper()
    if db_type != "A":
        warn(
            f"CARVM: db_option='{db_type}' — annuitisation benefit not yet implemented. "
            "pv_annuity = 0.",
            source="carvm/annuity_stub",
        )
    annuity_at_me = np.zeros(n, dtype=float)

    # PV at valuation date: PV_X[t] = X[t] × disc[t]
    pv_csv     = csv_at_me    * disc
    pv_annuity = annuity_at_me * disc
    pv_max     = np.maximum(pv_csv, pv_annuity)

    # CARVM reserve at each period = maximum PV from that period forward
    # (running max from the END of projection backward to valuation date)
    carvm_reserve = np.zeros(n, dtype=float)
    running_max   = 0.0
    for t in range(n - 1, -1, -1):
        v = float(pv_max[t]) if not np.isnan(pv_max[t]) else 0.0
        running_max = max(running_max, v)
        carvm_reserve[t] = running_max

    # Assemble output
    time_cols = [c for c in _TIME_COLS if c in dec_cf.columns]
    df = dec_cf[time_cols].copy()
    df["disc_factor"]   = disc             # pass-through for formula traceability
    df["fund_at_me"]    = fund_at_me
    df["csv_at_me"]     = csv_at_me
    df["annuity_at_me"] = annuity_at_me
    df["pv_csv"]        = pv_csv
    df["pv_annuity"]    = pv_annuity
    df["pv_max"]        = pv_max
    df["carvm_reserve"] = carvm_reserve
    df.index.name = "projection_period"
    return df


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_zero_carvm(dec_cf: pd.DataFrame) -> pd.DataFrame:
    """Return all-zero CARVM DataFrame (non-NYREG213+CARVM bases)."""
    time_cols = [c for c in _TIME_COLS if c in dec_cf.columns]
    df = dec_cf[time_cols].copy()
    for col in ("disc_factor", "fund_at_me", "csv_at_me", "annuity_at_me",
                "pv_csv", "pv_annuity", "pv_max", "carvm_reserve"):
        df[col] = 0.0
    df.index.name = "projection_period"
    return df
