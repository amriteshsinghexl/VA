"""
§9 — Lapse Engines

Implements the lapse decrement for each reserve basis, matching
Calc_Lapse_VM21PA / Calc_Lapse_VM21CA / Calc_Lapse_NYREG213.

Engine selection:
  reserve_basis == 'VM21PA' or 'GAAPDAC' → VM21PA engine
  reserve_basis == 'VM21CA'               → VM21CA engine (NaN — table data masked)
  reserve_basis == 'NYREG213'             → NYREG213 engine (NaN — table data masked)
  reserve_basis == 'CAPITAL'              → zero-lapse override (D-006)

VM21PA engine formula:
  1. benefit_base   = 4later_current_income_base (i4L GLB), or total_account_value if absent
  2. ITM_raw        = benefit_base / total_account_value  (static at valuation date —
                       dynamic ITM needs cashflow-engine AV series; simplified here)
  3. ITM_bucket     = floor(ITM_raw / 0.25) × 0.25, capped at table max row index
  4. sc_flag        = 3 if all surrender_charge_premium_* == 0, else 1
                       (periods 2+ retain the same sc_flag — D-014 documents this
                        simplification; true SC flag is a running per-bucket count)
  5. q_annual       = VM21PA_BaseLapseRates_{Non403b|403b}.loc[ITM_bucket, sc_flag]
  6. q_monthly      = 1 − (1 − q_annual)^(1/12)   [geometric monthly conversion]

Dynamic lapse:
  VM21PA_DynLapse_LifeFactors and VM21PA_DynLapse_DefFactors are empty in
  the sandbox workbook — dynamic-lapse adjustment = 0 for VM21PA.

Special cases (DISCREPANCIES.md):
  D-006: CAPITAL basis → q_monthly = 0.0 for all periods.
  D-008: NYREG213 + CARVM → AL-column (advanced lapse) result = 0.0.
         (This column is not separately tracked here; the calling engine must
          set it to 0.0 when config.nyreg213_carvm_zero_lapse is True.)
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from loaders.warnings import warn

# VM21PA lapse table ITM step size
_VM21PA_ITM_STEP = 0.25

# Column headers for the SC flag columns in the VM21PA lapse table
# (integer 1, 2, 3 matching the extracted column headers)
_SC_FLAG_COL = {1: 1, 2: 2, 3: 3}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_lapse(
    time_axis: pd.DataFrame,
    policy: dict[str, Any],
    assumptions: dict[str, pd.DataFrame],
    config: Any,
) -> pd.DataFrame:
    """
    Build the lapse-rate DataFrame for one policy.

    Parameters
    ----------
    time_axis   : output of decrements.time_axis.build_time_axis()
    policy      : output of loaders.policy_loader.load_policy()
    assumptions : output of loaders.assumption_loader.load_assumptions()
    config      : config.Config instance

    Returns
    -------
    DataFrame (index=projection_period) with columns:
        policy_year, policy_month, month_in_policy_year,
        bop_date, eop_date, cal_month_end, attained_age,
        sc_flag, itm_raw, itm_bucket,
        q_lapse_annual, q_lapse_monthly
    """
    basis = config.reserve_basis

    if basis == "CAPITAL":
        return _build_zero_lapse(time_axis)

    if basis in ("VM21PA", "GAAPDAC"):
        return _build_vm21pa_lapse(time_axis, policy, assumptions)

    if basis == "VM21CA":
        warn(
            "VM21CA lapse table data is masked in sandbox — q_lapse_monthly = NaN.",
            source="lapse/VM21CA",
        )
        return _build_nan_lapse(time_axis)

    if basis == "NYREG213":
        return _build_nyreg213_lapse(time_axis, policy, assumptions, config)

    warn(
        f"Unrecognised reserve_basis '{basis}' — returning NaN lapse.",
        source="lapse/unknown_basis",
    )
    return _build_nan_lapse(time_axis)


# ---------------------------------------------------------------------------
# VM21PA engine
# ---------------------------------------------------------------------------

def _build_vm21pa_lapse(
    time_axis: pd.DataFrame,
    policy: dict[str, Any],
    assumptions: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """VM21PA lapse engine: ITM × SC-flag lookup in VM21PA_BaseLapseRates_Non403b."""
    is_403b = bool(policy.get("indicator_401k", False))
    tbl_key = "VM21PA_BaseLapseRates_403b" if is_403b else "VM21PA_BaseLapseRates_Non403b"
    lapse_tbl = assumptions.get(tbl_key)
    if lapse_tbl is None or lapse_tbl.empty:
        warn(
            f"Lapse table '{tbl_key}' not found or empty — q_lapse_monthly = NaN.",
            source="lapse/VM21PA",
        )
        return _build_nan_lapse(time_axis)

    # ITM (static at valuation date — simplified)
    benefit_base = _benefit_base(policy)
    av = float(policy.get("total_account_value", 0) or 0)
    itm_raw = (benefit_base / av) if av > 0 else 0.0

    # ITM bucket: floor to nearest ITM_STEP, cap at table max index
    itm_max = float(lapse_tbl.index.max()) if not is_403b else np.nan
    itm_bucket = _itm_bucket(itm_raw, _VM21PA_ITM_STEP, itm_max)

    # SC flag (static — see module docstring for D-014 caveat)
    sc_flag = _sc_flag_from_policy(policy)

    records: list[dict] = []
    for period, row in time_axis.iterrows():
        q_annual = _vm21pa_lookup(lapse_tbl, itm_bucket, sc_flag, tbl_key, is_403b)
        q_monthly = _geometric_monthly(q_annual)

        records.append({
            "policy_year":          row["policy_year"],
            "policy_month":         row["policy_month"],
            "month_in_policy_year": int(row["month_in_policy_year"]),
            "bop_date":             row["bop_date"],
            "eop_date":             row["eop_date"],
            "cal_month_end":        row["cal_month_end"],
            "attained_age":         int(row["attained_age"]),
            "sc_flag":              sc_flag,
            "itm_raw":              itm_raw,
            "itm_bucket":           itm_bucket,
            "q_lapse_annual":       q_annual,
            "q_lapse_monthly":      q_monthly,
        })

    df = pd.DataFrame(records, index=time_axis.index)
    df.index.name = "projection_period"
    return df


def _vm21pa_lookup(
    tbl: pd.DataFrame,
    itm_bucket: float,
    sc_flag: int,
    tbl_key: str,
    is_403b: bool,
) -> float:
    """Look up annual lapse rate from VM21PA lapse table."""
    try:
        if is_403b:
            # 403b table: positional row = policy year (not ITM-indexed)
            # Use sc_flag as approximate column; table may have different structure
            val = tbl.iloc[min(0, len(tbl) - 1)][sc_flag]
        else:
            # Non-403b: indexed by ITM float, columns = sc_flag integers
            val = tbl.loc[itm_bucket, sc_flag]
    except (KeyError, IndexError):
        warn(
            f"Lapse lookup failed: table={tbl_key}, ITM={itm_bucket}, sc_flag={sc_flag}",
            source="lapse/VM21PA_lookup",
        )
        return np.nan

    if val is None:
        return np.nan
    try:
        f = float(val)
        return np.nan if math.isnan(f) else f
    except (TypeError, ValueError):
        return np.nan


# ---------------------------------------------------------------------------
# NYREG213 engine
# ---------------------------------------------------------------------------

def _build_nyreg213_lapse(
    time_axis: pd.DataFrame,
    policy: dict[str, Any],
    assumptions: dict[str, pd.DataFrame],
    config: Any,
) -> pd.DataFrame:
    """
    NYREG213 lapse engine.

    Base lapse from NYREG213_DynLapse_LifeFactors_{M|F|U} (150 ITM × 100 duration).
    D-008: when config.nyreg213_carvm_zero_lapse is True, AL column = 0.0.

    Dynamic lapse table is DUMMY-masked in sandbox — q_lapse_monthly will be NaN.
    """
    gender = str(policy.get("gender1", "U"))
    gender_suffix = {"M": "M", "F": "F"}.get(gender, "U")
    life_key = f"NYREG213_DynLapse_LifeFactors_{gender_suffix}"
    life_tbl = assumptions.get(life_key)

    if life_tbl is None or life_tbl.empty:
        warn(
            f"NYREG213 lapse table '{life_key}' not found or empty — "
            f"q_lapse_monthly = NaN.",
            source="lapse/NYREG213",
        )
        return _build_nan_lapse(time_axis)

    benefit_base = _benefit_base(policy)
    av = float(policy.get("total_account_value", 0) or 0)
    itm_raw = (benefit_base / av) if av > 0 else 0.0

    records: list[dict] = []
    for period, row in time_axis.iterrows():
        pol_year = int(row["policy_year"])
        dur_col = min(pol_year, 100)  # table has columns 1..100

        # ITM row: scale ITM_raw to table row index (table has 150 rows)
        # Row index is 0-based; assuming ITM scale 0..∞ mapped to rows 0..149
        itm_row = min(int(itm_raw / 0.01), 149)  # 0.01 per row (approximate)

        q_annual = np.nan
        try:
            val = life_tbl.iloc[itm_row][dur_col]
            if val is not None:
                f = float(val)
                if not math.isnan(f):
                    q_annual = f / 100.0  # table values are percentages
        except (KeyError, IndexError, TypeError, ValueError):
            pass

        q_monthly = _geometric_monthly(q_annual)

        # D-008: NYREG213 + CARVM → AL column = 0.0
        # AL column corresponds to q_lapse_monthly here
        if config.nyreg213_carvm_zero_lapse:
            q_monthly = 0.0

        records.append({
            "policy_year":          row["policy_year"],
            "policy_month":         row["policy_month"],
            "month_in_policy_year": int(row["month_in_policy_year"]),
            "bop_date":             row["bop_date"],
            "eop_date":             row["eop_date"],
            "cal_month_end":        row["cal_month_end"],
            "attained_age":         int(row["attained_age"]),
            "sc_flag":              np.nan,
            "itm_raw":              itm_raw,
            "itm_bucket":           float(itm_row),
            "q_lapse_annual":       q_annual,
            "q_lapse_monthly":      q_monthly,
        })

    df = pd.DataFrame(records, index=time_axis.index)
    df.index.name = "projection_period"
    return df


# ---------------------------------------------------------------------------
# Special-case builders
# ---------------------------------------------------------------------------

def _build_zero_lapse(time_axis: pd.DataFrame) -> pd.DataFrame:
    """D-006: CAPITAL basis — all lapse rates = 0.0."""
    records = []
    for period, row in time_axis.iterrows():
        records.append({
            "policy_year":          row["policy_year"],
            "policy_month":         row["policy_month"],
            "month_in_policy_year": int(row["month_in_policy_year"]),
            "bop_date":             row["bop_date"],
            "eop_date":             row["eop_date"],
            "cal_month_end":        row["cal_month_end"],
            "attained_age":         int(row["attained_age"]),
            "sc_flag":              np.nan,
            "itm_raw":              np.nan,
            "itm_bucket":           np.nan,
            "q_lapse_annual":       0.0,
            "q_lapse_monthly":      0.0,
        })
    df = pd.DataFrame(records, index=time_axis.index)
    df.index.name = "projection_period"
    return df


def _build_nan_lapse(time_axis: pd.DataFrame) -> pd.DataFrame:
    """Return a lapse DataFrame with NaN for all computed lapse columns."""
    records = []
    for period, row in time_axis.iterrows():
        records.append({
            "policy_year":          row["policy_year"],
            "policy_month":         row["policy_month"],
            "month_in_policy_year": int(row["month_in_policy_year"]),
            "bop_date":             row["bop_date"],
            "eop_date":             row["eop_date"],
            "cal_month_end":        row["cal_month_end"],
            "attained_age":         int(row["attained_age"]),
            "sc_flag":              np.nan,
            "itm_raw":              np.nan,
            "itm_bucket":           np.nan,
            "q_lapse_annual":       np.nan,
            "q_lapse_monthly":      np.nan,
        })
    df = pd.DataFrame(records, index=time_axis.index)
    df.index.name = "projection_period"
    return df


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _benefit_base(policy: dict[str, Any]) -> float:
    """
    Select the GLB benefit base to use for ITM calculation.

    Priority:
      1. i4L benefit → 4later_current_income_base
      2. GMWB benefit → gmwb_current_benefit_base (when > 0)
      3. Fallback → total_account_value (ITM = 1.0)
    """
    i4l_base = policy.get("4later_current_income_base")
    if i4l_base is not None:
        try:
            v = float(i4l_base)
            if v > 0:
                return v
        except (TypeError, ValueError):
            pass

    gmwb_base = policy.get("gmwb_current_benefit_base")
    if gmwb_base is not None:
        try:
            v = float(gmwb_base)
            if v > 0:
                return v
        except (TypeError, ValueError):
            pass

    return float(policy.get("total_account_value", 0) or 0)


def _itm_bucket(itm_raw: float, step: float, itm_max: float) -> float:
    """
    Convert raw ITM to the nearest bucket ≤ itm_raw.

    Uses floor division by step, then caps at itm_max.
    """
    if math.isnan(itm_raw) or math.isnan(itm_max):
        return 0.0
    bucket = math.floor(itm_raw / step) * step
    return min(bucket, itm_max)


def _sc_flag_from_policy(policy: dict[str, Any]) -> int:
    """
    Determine the surrender-charge period flag (1, 2, or 3) from policy data.

    Rule (simplified — see D-014):
      All surrender_charge_premium_* == 0  → flag 3 (post-SC)
      Any surrender_charge_premium_* > 0   → flag 1 (within SC)

    A full implementation would track the SC schedule bucket-by-bucket and
    determine the exact period for each projection step.
    """
    for i in range(10):
        key = f"surrender_charge_premium_{i}"
        val = policy.get(key, 0)
        try:
            if float(val or 0) > 0:
                return 1
        except (TypeError, ValueError):
            pass
    return 3


def _geometric_monthly(q_annual: float) -> float:
    """
    Convert annual lapse rate to monthly via geometric distribution.

    q_m = 1 − (1 − q_a)^(1/12)

    Returns NaN if q_annual is NaN, negative, or ≥ 1.0.
    """
    if math.isnan(q_annual):
        return np.nan
    if q_annual < 0.0 or q_annual >= 1.0:
        return np.nan
    return 1.0 - (1.0 - q_annual) ** (1.0 / 12.0)
