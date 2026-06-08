"""
§11 — Fund Mechanics Engine  (Step 12)

Computes the monthly equity growth factor for each of the 6 separate-account
investment accounts for every projection period.

Formula (VM21PA / VM21CA / GAAPDAC / CAPITAL — stochastic scenario path):
  r_annual[t] = (EQ_Growth_pct[t] + EQ_Income_pct[t]) / 100
  growth_factor[t] = (1 + r_annual[t])^(1/12) − 1

This is the "g" used in the AV waterfall as:
  fund_growth_amount = AV_after_charges × g

Six investment accounts (Inv Acct # from workbook Calc_SepAcct stack headers):
  Fund 1: S&P 500
  Fund 2: Russell 2000
  Fund 3: Risk-Managed Fund
  Fund 4: MSCI EAFE
  Fund 5: Money Market
  Fund 6: Barclays Capital Aggregate

Stub period = 0 throughout (D-005), so the full monthly growth is applied
BOP-to-CME and zero growth is applied CME-to-EOP.  The EOP portion is therefore
zero and not computed here.

NYREG213 (StdScn) prescribed growth:
  Uses tables NYREG213_StdScn_GrowthRates_202* and _Pre* from
  Assumptions_Extracted.xlsx, selected per fund's BD$8 type (Equity/Bond).
  Not yet implemented; columns will contain NaN with a ModelWarning until
  this path is added.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Any

from loaders.warnings import warn

# ---------------------------------------------------------------------------
# Fund catalogue — matches workbook Calc_SepAcct stack layout
# ---------------------------------------------------------------------------

_FUNDS = [
    {
        "index":      1,
        "col":        "growth_f1",
        "name":       "S&P 500",
        "growth_var": "S&P 500-EQ_Growth",
        "income_var": "S&P 500-EQ_Income",
    },
    {
        "index":      2,
        "col":        "growth_f2",
        "name":       "Russell 2000",
        "growth_var": "Russell 2000-EQ_Growth",
        "income_var": "Russell 2000-EQ_Income",
    },
    {
        "index":      3,
        "col":        "growth_f3",
        "name":       "Risk-Managed Fund",
        "growth_var": "Risk-Managed Fund-EQ_Growth",
        "income_var": "Risk-Managed Fund-EQ_Income",
    },
    {
        "index":      4,
        "col":        "growth_f4",
        "name":       "MSCI EAFE",
        "growth_var": "MSCI EAFE-EQ_Growth",
        "income_var": "MSCI EAFE-EQ_Income",
    },
    {
        "index":      5,
        "col":        "growth_f5",
        "name":       "Money Market",
        "growth_var": "Money Market-EQ_Growth",
        "income_var": "Money Market-EQ_Income",
    },
    {
        "index":      6,
        "col":        "growth_f6",
        "name":       "Barclays Capital Aggregate",
        "growth_var": "Barclays Capital Aggregate-EQ_Growth",
        "income_var": "Barclays Capital Aggregate-EQ_Income",
    },
]

_TIME_COLS = [
    "policy_year", "policy_month", "month_in_policy_year",
    "bop_date", "eop_date", "cal_month_end", "attained_age",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_fund_mechanics(
    time_axis: pd.DataFrame,
    scenarios,           # ScenarioData from loaders.scenario_loader
    config: Any,
) -> pd.DataFrame:
    """
    Build the monthly fund growth factor spine for all 6 investment accounts.

    Parameters
    ----------
    time_axis : output of decrements.time_axis.build_time_axis()
    scenarios : output of loaders.scenario_loader.load_scenarios()
    config    : config.Config (uses config.reserve_basis for NYREG213 dispatch)

    Returns
    -------
    DataFrame (index=projection_period) with columns:
        policy_year, policy_month, month_in_policy_year,
        bop_date, eop_date, cal_month_end, attained_age,
        growth_f1 … growth_f6
        (monthly decimal factor, e.g. 0.00917 means +0.917% for the month)
    """
    if time_axis.empty:
        warn("time_axis is empty — returning empty fund_mechanics DataFrame.",
             source="fund_mechanics/empty_time_axis")
        return pd.DataFrame()

    basis = getattr(config, "reserve_basis", "VM21PA")

    if basis == "NYREG213":
        warn(
            "NYREG213 prescribed growth rates not yet implemented — "
            "growth_f1..f6 will be NaN.  Populate from "
            "NYREG213_StdScn_GrowthRates tables in a future step.",
            source="fund_mechanics/nyreg213_stub",
        )
        return _build_nan_mechanics(time_axis)

    # Stochastic path: VM21PA, VM21CA, GAAPDAC, CAPITAL
    return _build_stochastic_mechanics(time_axis, scenarios)


# ---------------------------------------------------------------------------
# Stochastic path (VM21PA / VM21CA / GAAPDAC / CAPITAL)
# ---------------------------------------------------------------------------

def _build_stochastic_mechanics(
    time_axis: pd.DataFrame,
    scenarios,
) -> pd.DataFrame:
    """Compute (1 + r_annual)^(1/12) - 1 from EQ_Growth + EQ_Income scenario series."""
    idx = time_axis.index
    n   = len(idx)

    time_cols = [c for c in _TIME_COLS if c in time_axis.columns]
    df = time_axis[time_cols].copy()

    for fund in _FUNDS:
        growth_pct = _fetch_series(scenarios, fund["growth_var"], idx, n,
                                   fund["name"], "EQ_Growth")
        income_pct = _fetch_series(scenarios, fund["income_var"], idx, n,
                                   fund["name"], "EQ_Income")

        # Combine: total annual return as decimal
        r_annual = (growth_pct + income_pct) / 100.0

        # Monthly compounding factor: (1+r)^(1/12) − 1
        monthly_factor = (1.0 + r_annual) ** (1.0 / 12.0) - 1.0

        df[fund["col"]] = monthly_factor

    df.index.name = "projection_period"
    return df


def _fetch_series(
    scenarios,
    var_name: str,
    idx,
    n: int,
    fund_name: str,
    rate_type: str,
) -> np.ndarray:
    """
    Pull a scenario variable into a length-n float array aligned to idx.

    Missing variable → NaN array + ModelWarning.
    Missing individual periods → NaN for that period.
    """
    try:
        series = scenarios.get(var_name)
    except KeyError:
        warn(
            f"Scenario variable '{var_name}' not found for fund '{fund_name}' "
            f"({rate_type}) — growth factor will be NaN.",
            source=f"fund_mechanics/missing_{rate_type}",
        )
        return np.full(n, np.nan)

    arr = np.empty(n, dtype=float)
    for k, period in enumerate(idx):
        val = series.get(period) if hasattr(series, "get") else (
            series.loc[period] if period in series.index else None
        )
        arr[k] = float(val) if (val is not None and not _is_nan(val)) else np.nan

    return arr


# ---------------------------------------------------------------------------
# NYREG213 stub
# ---------------------------------------------------------------------------

def _build_nan_mechanics(time_axis: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame of NaN growth factors (NYREG213 stub)."""
    time_cols = [c for c in _TIME_COLS if c in time_axis.columns]
    df = time_axis[time_cols].copy()
    for fund in _FUNDS:
        df[fund["col"]] = np.nan
    df.index.name = "projection_period"
    return df


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _is_nan(x) -> bool:
    """True if x is float NaN or None."""
    if x is None:
        return True
    try:
        return np.isnan(float(x))
    except (TypeError, ValueError):
        return True
