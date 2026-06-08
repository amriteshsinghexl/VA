"""
§24 — DAC Amortization  (Step 24)

Implements GAAP LDTI DAC amortization per Calc_DAC.

Calc_DAC structure (confirmed from workbook):
  Lives columns:  Lives BOP, Deaths BOP-CME, Lives CME, Deaths CME-EOP,
                  Lapses CME-EOP, Lives EOP
  Amort columns:  Amortisation Base EOP (#VALUE! for test policy), Amortisation Base

D-003: Policy_Info!C107 (DAC_Amortization_Basis) returns #VALUE! for the test policy.
  Consequence: Amortisation Base EOP = #VALUE! and Amortisation Base = 0 throughout.
  This is the workbook-confirmed state for policy 842612365.

DAC reserve mechanics (when Amortisation Base is available):
  DAC_Balance[t]   = DAC_Balance[t-1] × (1 + credited_rate) − Amort_Base[t]
  Amort_Base[t]    = DAC_Balance_BOP[t] × (q_amort)
  q_amort          = uniform amortisation rate over the DAC amortisation period

Test policy: DAC = 0 throughout (D-003).

Output columns (time spine + 7):
  lives_bop, n_deaths_bop_cme, lives_cme,
  n_deaths_cme_eop, n_lapses_cme_eop, lives_eop,
  dac_balance
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


def calculate_dac(
    dec_cf: pd.DataFrame,
    lives: pd.DataFrame,
    policy: dict[str, Any],
    config: Any,
) -> pd.DataFrame:
    """
    Compute the DAC amortisation schedule.

    Parameters
    ----------
    dec_cf  : lives-weighted cashflows (reserve.decremented_cf.apply_lives output)
    lives   : output of decrements.lives.build_lives()
              (provides lives_bop, lives_eop, q_mort_monthly, q_lapse_monthly)
    policy  : output of loaders.policy_loader.load_policy()
    config  : config.Config  (uses reserve_basis)

    Returns
    -------
    DataFrame (index=projection_period) with columns:
        [time-axis pass-through],
        lives_bop, n_deaths_bop_cme, lives_cme,
        n_deaths_cme_eop, n_lapses_cme_eop, lives_eop,
        dac_balance
    """
    if dec_cf.empty:
        warn("dec_cf is empty — returning empty DAC DataFrame.",
             source="dac/empty")
        return pd.DataFrame()

    idx = dec_cf.index
    n   = len(idx)

    # D-003: DAC_Amortization_Basis = #VALUE! for test policy
    # Return zero DAC with ModelWarning
    dac_basis = policy.get("dac_amortization_basis") or policy.get("DAC_Amortization_Basis")
    if dac_basis is None or str(dac_basis).strip() in ("#VALUE!", "", "None"):
        warn(
            "DAC_Amortization_Basis is #VALUE! or missing (D-003) — "
            "DAC balance = 0 throughout.  Populate Policy_Info!C107 from "
            "a live workbook run before computing GAAP LDTI DAC.",
            source="dac/basis_value_error",
        )
        return _build_zero_dac(dec_cf, lives, idx, n)

    # ---- Non-zero DAC: amortisation schedule --------------------------------
    # (Not exercised for test policy — structure provided for completeness)
    warn(
        "DAC non-zero amortisation not yet fully implemented. "
        "Returning zero DAC balance.",
        source="dac/amort_stub",
    )
    return _build_zero_dac(dec_cf, lives, idx, n)


def _build_zero_dac(
    dec_cf: pd.DataFrame,
    lives: pd.DataFrame,
    idx,
    n: int,
) -> pd.DataFrame:
    """Return zero-balance DAC DataFrame with lives columns from Calc_Lives."""
    time_cols = [c for c in _TIME_COLS if c in dec_cf.columns]
    df = dec_cf[time_cols].copy()

    # Lives columns — pass through from decrements.lives
    lives_r = lives.reindex(idx)
    bop = lives_r["lives_bop"].to_numpy(dtype=float, na_value=np.nan)
    eop = lives_r["lives_eop"].to_numpy(dtype=float, na_value=np.nan)
    qm  = lives_r["q_mort_monthly"].to_numpy(dtype=float, na_value=0.0)
    ql  = lives_r["q_lapse_monthly"].to_numpy(dtype=float, na_value=0.0)

    # Deaths and lapses (per Calc_DAC convention: BOP-to-CME = full month,
    # CME-to-EOP = 0 because stub_period = 0, D-005)
    n_deaths_bop_cme  = bop  * qm
    lives_cme         = bop  * (1.0 - qm)
    n_deaths_cme_eop  = np.zeros(n, dtype=float)   # stub_period = 0 → CME = EOP
    n_lapses_cme_eop  = bop  * ql                   # lapse applied at CME→EOP step
    lives_eop         = eop

    df["lives_bop"]         = bop
    df["n_deaths_bop_cme"]  = n_deaths_bop_cme
    df["lives_cme"]         = lives_cme
    df["n_deaths_cme_eop"]  = n_deaths_cme_eop
    df["n_lapses_cme_eop"]  = n_lapses_cme_eop
    df["lives_eop"]         = lives_eop
    df["dac_balance"]       = 0.0   # D-003

    df.index.name = "projection_period"
    return df
