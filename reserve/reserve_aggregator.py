"""
§25 — Reserve Aggregator  (Step 20c)

Combines the Standard Scenario ANR and other reserve components into the
final per-period reserve for the active reserve_basis + reserve_method.

Final reserve (VM21PA + StdScn):
  reserve[t] = max(0, anr[t])
  Final reserve at valuation date = reserve[1] (period 1 = valuation month)

For test policy 842612365 (VM21PA, StdScn):
  ANR = 0 for all periods → final reserve = $0.

Reserve summary columns:
  anr           : Standard Scenario ANR (= 0 for test policy)
  reserve       : max(0, anr) — the binding reserve each period
  reserve_t0    : reserve at valuation date (period 1)
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


def aggregate_reserves(
    std_scn: pd.DataFrame,
    carvm: pd.DataFrame,
    dac: pd.DataFrame,
    policy: dict[str, Any],
    config: Any,
) -> pd.DataFrame:
    """
    Produce the final reserve summary DataFrame.

    Binding reserve selection:
      VM21PA + StdScn  → max(0, std_scn.anr)
      NYREG213 + CARVM → max(0, carvm.carvm_reserve)
      Other bases      → std_scn.anr (fallback)

    DAC balance is additive to the reserve for GAAPDAC basis.

    Parameters
    ----------
    std_scn  : output of reserve.std_scn_anr.calculate_std_scn_anr()
    carvm    : output of reserve.carvm.calculate_carvm()
    dac      : output of reserve.dac.calculate_dac()
    policy   : output of loaders.policy_loader.load_policy()
    config   : config.Config

    Returns
    -------
    DataFrame (index=projection_period) with columns:
        [time-axis pass-through],
        anr, carvm_reserve, dac_balance,
        reserve, reserve_t0
    """
    if std_scn.empty:
        warn("std_scn is empty — returning empty reserve_aggregator DataFrame.",
             source="reserve_aggregator/empty")
        return pd.DataFrame()

    idx = std_scn.index

    anr_arr    = std_scn["anr"].to_numpy(dtype=float, na_value=0.0)
    carvm_arr  = (carvm.reindex(idx)["carvm_reserve"].to_numpy(dtype=float, na_value=0.0)
                  if not carvm.empty and "carvm_reserve" in carvm.columns
                  else np.zeros(len(idx), dtype=float))
    dac_arr    = (dac.reindex(idx)["dac_balance"].to_numpy(dtype=float, na_value=0.0)
                  if not dac.empty and "dac_balance" in dac.columns
                  else np.zeros(len(idx), dtype=float))

    # Select binding reserve per basis
    basis  = config.reserve_basis
    method = config.reserve_method

    if basis == "NYREG213" and method == "CARVM":
        reserve_arr = np.maximum(0.0, carvm_arr)
    elif basis == "GAAPDAC":
        reserve_arr = np.maximum(0.0, anr_arr) + np.maximum(0.0, dac_arr)
    else:
        # VM21PA, VM21CA, CAPITAL → StdScn ANR
        reserve_arr = np.maximum(0.0, anr_arr)

    reserve_t0 = float(reserve_arr[0]) if len(reserve_arr) > 0 else 0.0

    time_cols = [c for c in _TIME_COLS if c in std_scn.columns]
    df = std_scn[time_cols].copy()
    df["anr"]           = anr_arr
    df["carvm_reserve"] = carvm_arr
    df["dac_balance"]   = dac_arr
    df["reserve"]       = reserve_arr
    df["reserve_t0"]    = reserve_t0
    df.index.name = "projection_period"
    return df
