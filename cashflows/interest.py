"""
§11 — Interest Rate Engine

Converts scenario BEY (Bond Equivalent Yield) rates to monthly effective rates
and running discount factors.  Produces both unshocked and +100bps-shocked columns.

Formula chain (per projection period t):
  i_bey_pct[t]   = scenario value (percent, e.g. 3.98 means 3.98%)
  i_bey[t]       = i_bey_pct[t] / 100
  i_aey[t]       = (1 + i_bey[t]/2)^2 − 1         (semi-annual BEY → annual effective)
  i_monthly[t]   = (1 + i_aey[t])^(1/12) − 1      (annual → monthly effective)
  disc_factor[t] = disc_factor[t−1] / (1 + i_monthly[t])
                                                    (disc_factor[0] ≡ 1.0, not in output)

+100bps shock (applied at the AEY level, per workbook convention):
  i_aey_shock[t]       = i_aey[t] + 0.01
  i_monthly_shock[t]   = (1 + i_aey_shock[t])^(1/12) − 1
  disc_factor_shock[t] = running product of 1/(1 + i_monthly_shock[t])

NaN propagation:
  If the scenario row is missing or BEY is NaN, all derived quantities are NaN
  for that period and disc_factor propagates NaN to all later periods via cumprod.

Default tenor: 10YR (Interest-YC_10YR).  All tenors are identical for the test
scenario (flat yield curve); the tenor parameter is exposed for future use.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Any

from loaders.warnings import warn

_SHOCK_DECIMAL = 100 / 10_000    # +100bps expressed as a decimal (0.01)

_TIME_COLS = [
    "policy_year", "policy_month", "month_in_policy_year",
    "bop_date", "eop_date", "cal_month_end", "attained_age",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_interest_rates(
    time_axis: pd.DataFrame,
    scenarios,                    # ScenarioData from loaders.scenario_loader
    config: Any,
    *,
    tenor: str = "10YR",
) -> pd.DataFrame:
    """
    Build the interest rate and discount factor spine for one policy.

    Parameters
    ----------
    time_axis : output of decrements.time_axis.build_time_axis()
    scenarios : output of loaders.scenario_loader.load_scenarios()
    config    : config.Config instance (reserved for future use)
    tenor     : yield-curve tenor suffix, default "10YR"
                Looks up scenario variable "Interest-YC_{tenor}"

    Returns
    -------
    DataFrame (index=projection_period) with columns:
        policy_year, policy_month, month_in_policy_year,
        bop_date, eop_date, cal_month_end, attained_age,
        i_bey_pct, i_aey, i_monthly, disc_factor,
        i_aey_shock, i_monthly_shock, disc_factor_shock
    """
    if time_axis.empty:
        warn(
            "time_axis is empty — returning empty interest DataFrame.",
            source="interest/empty_time_axis",
        )
        return pd.DataFrame()

    var_name = f"Interest-YC_{tenor}"
    try:
        bey_series = scenarios.get(var_name)
    except KeyError:
        warn(
            f"Scenario variable '{var_name}' not found — all rates will be NaN.",
            source="interest/missing_variable",
        )
        bey_series = None

    idx = time_axis.index          # projection_period integers (1..N)
    n = len(idx)

    # Align scenario months (1..600) to projection_period (1..N)
    i_bey_pct = np.empty(n, dtype=float)
    for k, period in enumerate(idx):
        if bey_series is None:
            i_bey_pct[k] = np.nan
        else:
            val = bey_series.get(period) if hasattr(bey_series, "get") else (
                bey_series.loc[period] if period in bey_series.index else np.nan
            )
            i_bey_pct[k] = float(val) if (val is not None and not _is_nan(val)) else np.nan

    # ---- Conversion chain ----
    i_bey     = i_bey_pct / 100.0
    i_aey     = (1.0 + i_bey / 2.0) ** 2 - 1.0
    i_monthly = (1.0 + i_aey) ** (1.0 / 12.0) - 1.0
    disc_factor = _running_disc_factor(i_monthly)

    # ---- +100bps shock (at AEY level) ----
    i_aey_shock       = i_aey + _SHOCK_DECIMAL
    i_monthly_shock   = (1.0 + i_aey_shock) ** (1.0 / 12.0) - 1.0
    disc_factor_shock = _running_disc_factor(i_monthly_shock)

    # ---- Assemble output DataFrame ----
    time_cols = [c for c in _TIME_COLS if c in time_axis.columns]
    df = time_axis[time_cols].copy()
    df["i_bey_pct"]         = i_bey_pct
    df["i_aey"]             = i_aey
    df["i_monthly"]         = i_monthly
    df["disc_factor"]       = disc_factor
    df["i_aey_shock"]       = i_aey_shock
    df["i_monthly_shock"]   = i_monthly_shock
    df["disc_factor_shock"] = disc_factor_shock
    df.index.name = "projection_period"
    return df


# ---------------------------------------------------------------------------
# Core helper (exposed for unit testing)
# ---------------------------------------------------------------------------

def _running_disc_factor(i_monthly: np.ndarray) -> np.ndarray:
    """
    Compute the running discount factor from an array of monthly effective rates.

    disc_factor[t] = product_{k=0}^{t} 1/(1 + i_monthly[k])

    with the implicit initial condition disc_factor[-1] = 1.0 (not in output).

    NaN in i_monthly propagates to that element and all subsequent via cumprod.
    """
    v = 1.0 / (1.0 + i_monthly)   # per-period discount factors (element-wise)
    return np.cumprod(v)


def _is_nan(x) -> bool:
    """Return True if x is float NaN or None."""
    if x is None:
        return True
    try:
        return np.isnan(float(x))
    except (TypeError, ValueError):
        return True
