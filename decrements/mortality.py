"""
§8 — Mortality Engine

16-column Calc_Mortality projection aligned to the time axis.

Columns (matching workbook Calc_Mortality A–P):
  A  projection_period      (index, from time_axis)
  B  policy_year
  C  policy_month
  D  month_in_policy_year
  E  bop_date
  F  eop_date
  G  cal_month_end
  H  attained_age
  I  q_annual               Annual base mortality rate (positional age lookup)
  J  pad                    PAD multiplier — 1.0 per workbook for all supported bases
  K  imp_scale              Annual improvement scale (positional age lookup, capped age 119)
  L  years_imp              cal_month_end.year − base_year  (base_year from sheet meta)
  M  imp_mult               (1 − imp_scale) ^ years_imp
  N  add_mult               Additional multiplier from factor table (addl_desc column)
  O  final_ann              q_annual × pad × imp_mult × add_mult
  P  q_monthly              UDD: (final_ann/12) / (1 − (month_in_policy_year−1)/12 × final_ann)

Table prefix logic:
  VM21PA  → VM21PA_BaseMortality_Single, VM21PA_MortalityImprovement, VM21PA_MortalityFactor_Addition
  VM21CA  → VM21CA_* (same pattern)
  NYREG213 → NYREG213_* (same pattern; no MortalityFactor_Addition for NYREG213)
  GAAPDAC, CAPITAL → default to VM21PA tables

AddMult column descriptor:
  i4l_indicator == 'i4L'  → 'WithGLB_{Male|Female}'
  otherwise               → 'Other_{Male|Female}'

Note: All base mortality, improvement-scale, and add-mult tables in the
sandbox Assumptions_Extracted.xlsx are masked with RAND()/10 floats.
Numerical outputs will not match production values, but formula structure
and column layout are correct.
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

def build_mortality(
    time_axis: pd.DataFrame,
    policy: dict[str, Any],
    assumptions: dict[str, pd.DataFrame],
    config: Any,
) -> pd.DataFrame:
    """
    Build the 16-column Calc_Mortality DataFrame for one policy.

    Parameters
    ----------
    time_axis    : output of decrements.time_axis.build_time_axis()
    policy       : output of loaders.policy_loader.load_policy()
    assumptions  : output of loaders.assumption_loader.load_assumptions()
    config       : config.Config instance

    Returns
    -------
    DataFrame indexed by projection_period (1..N) with 15 columns:
        policy_year, policy_month, month_in_policy_year,
        bop_date, eop_date, cal_month_end, attained_age,
        q_annual, pad, imp_scale, years_imp, imp_mult,
        add_mult, final_ann, q_monthly
    """
    prefix = _mortality_prefix(config)

    base_key = f"{prefix}_BaseMortality_Single"
    imp_key  = f"{prefix}_MortalityImprovement"
    # D-012: NYREG213 factor table is 'NYREG213_MortalityFactor' (no '_Addition' suffix)
    add_key  = (
        "NYREG213_MortalityFactor"
        if prefix == "NYREG213"
        else f"{prefix}_MortalityFactor_Addition"
    )

    base_tbl = assumptions.get(base_key)
    imp_tbl  = assumptions.get(imp_key)
    add_tbl  = assumptions.get(add_key)

    for key, tbl in ((base_key, base_tbl), (imp_key, imp_tbl)):
        if tbl is None:
            warn(
                f"Mortality table '{key}' not found in assumptions — "
                f"affected columns will be NaN.",
                source="mortality/table_lookup",
            )
    if add_tbl is None:
        warn(
            f"Mortality factor table '{add_key}' not found in assumptions — "
            f"add_mult will be NaN (treat as 1.0 if intentional).",
            source="mortality/table_lookup",
        )

    # Improvement base year — stored as a scalar in hdr_row4 of the imp sheet
    base_year: int | None = None
    if imp_tbl is not None:
        by = imp_tbl.attrs.get("meta", {}).get("hdr_row4")
        if by is not None:
            try:
                by_f = float(by)
                if not math.isnan(by_f):
                    base_year = int(by_f)
            except (TypeError, ValueError):
                pass
    if base_year is None:
        warn(
            f"Improvement base year not found in '{imp_key}' meta['hdr_row4'] — "
            f"years_imp and imp_mult will be NaN.",
            source="mortality/base_year",
        )

    gender    = str(policy.get("gender1", "M"))
    addl_desc = _addl_desc(policy, prefix)

    records: list[dict] = []
    for period, row in time_axis.iterrows():
        age      = int(row["attained_age"])
        mo_in_yr = int(row["month_in_policy_year"])
        cal_year = row["cal_month_end"].year

        # I — q_annual: positional age lookup in base mortality table
        q_a = _lookup_by_age(base_tbl, age, gender)

        # J — pad: 1.0 per workbook (no PAD adjustment in Calc_Mortality)
        pad = 1.0

        # K — imp_scale: improvement scale, age capped at 119
        # D-013: VM21PA_MortalityImprovement has no 'F' column — fall back to 'U' (unisex)
        imp_age   = min(age, 119)
        imp_scale = _lookup_by_age(imp_tbl, imp_age, gender)
        if math.isnan(imp_scale) and gender != "U":
            imp_scale = _lookup_by_age(imp_tbl, imp_age, "U")

        # L — years_imp
        years_imp: float = float(cal_year - base_year) if base_year is not None else np.nan

        # M — imp_mult = (1 − imp_scale)^years_imp
        imp_mult = _imp_mult(imp_scale, years_imp)

        # N — add_mult: additional factor, column = addl_desc
        add_mult = _lookup_by_age(add_tbl, age, addl_desc)

        # O — final_ann
        final_ann = _product_or_nan(q_a, pad, imp_mult, add_mult)

        # P — q_monthly (UDD)
        q_monthly = _udd(final_ann, mo_in_yr)

        records.append({
            "policy_year":          row["policy_year"],
            "policy_month":         row["policy_month"],
            "month_in_policy_year": mo_in_yr,
            "bop_date":             row["bop_date"],
            "eop_date":             row["eop_date"],
            "cal_month_end":        row["cal_month_end"],
            "attained_age":         age,
            "q_annual":             q_a,
            "pad":                  pad,
            "imp_scale":            imp_scale,
            "years_imp":            years_imp,
            "imp_mult":             imp_mult,
            "add_mult":             add_mult,
            "final_ann":            final_ann,
            "q_monthly":            q_monthly,
        })

    df = pd.DataFrame(records, index=time_axis.index)
    df.index.name = "projection_period"
    return df


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mortality_prefix(config: Any) -> str:
    """
    Map config.reserve_basis to assumption table name prefix.

    VM21CA, VM21PA, NYREG213 → use their own prefix.
    GAAPDAC, CAPITAL → fall back to VM21PA (standard principal assumption).
    """
    basis = config.reserve_basis
    if basis in ("VM21CA", "VM21PA", "NYREG213"):
        return basis
    return "VM21PA"


def _addl_desc(policy: dict[str, Any], prefix: str) -> str:
    """
    Return the add_mult lookup column name for this policy and table prefix.

    VM21PA / VM21CA (MortalityFactor_Addition):
      i4L indicator → 'WithGLB_{Male|Female}'
      otherwise     → 'Other_{Male|Female}'

    NYREG213 (MortalityFactor — D-012, rider-type columns):
      i4L indicator → 'Lifetime'
      otherwise     → 'None'
    """
    if prefix == "NYREG213":
        return "Lifetime" if str(policy.get("i4l_indicator", "")) == "i4L" else "None"
    gender_full = "Male" if str(policy.get("gender1", "M")) == "M" else "Female"
    if str(policy.get("i4l_indicator", "")) == "i4L":
        return f"WithGLB_{gender_full}"
    return f"Other_{gender_full}"


def _lookup_by_age(
    table: pd.DataFrame | None,
    age: int,
    col: str,
) -> float:
    """
    Positional row lookup: table.iloc[age][col].

    Age column in assumption tables is masked (RAND() float), so we cannot
    use label-based index lookups — positional iloc is required.
    The table is assumed to be ordered age 0, 1, 2, …, so iloc[age] = age data.

    Returns np.nan on any failure: missing table, out-of-range, missing
    column, non-numeric, or explicit None.
    """
    if table is None or table.empty:
        return np.nan
    row_idx = min(age, len(table) - 1)
    try:
        val = table.iloc[row_idx][col]
    except (KeyError, IndexError):
        return np.nan
    if val is None:
        return np.nan
    try:
        f = float(val)
        return np.nan if math.isnan(f) else f
    except (TypeError, ValueError):
        return np.nan


def _imp_mult(imp_scale: float, years_imp: float) -> float:
    """
    Improvement multiplier: (1 − imp_scale) ^ years_imp.

    Returns NaN when either input is NaN or when (1 − imp_scale) < 0
    (which would produce a complex result for fractional exponents).
    """
    if math.isnan(imp_scale) or math.isnan(years_imp):
        return np.nan
    base = 1.0 - imp_scale
    if base < 0.0:
        return np.nan
    return base ** years_imp


def _product_or_nan(*factors: float) -> float:
    """Multiply all factors; short-circuit to NaN on first NaN factor."""
    result = 1.0
    for f in factors:
        if math.isnan(f):
            return np.nan
        result *= f
    return result


def _udd(final_ann: float, month_in_policy_year: int) -> float:
    """
    UDD monthly mortality rate conversion.

    q_m = (q_a / 12) / (1 − (m − 1) / 12 × q_a)

    Returns NaN if final_ann is NaN, negative, or ≥ 1.0
    (protecting against division-by-zero and non-sensical inputs).
    """
    if math.isnan(final_ann):
        return np.nan
    if final_ann < 0.0 or final_ann >= 1.0:
        return np.nan
    denom = 1.0 - (month_in_policy_year - 1) / 12.0 * final_ann
    if denom <= 0.0:
        return np.nan
    return (final_ann / 12.0) / denom
