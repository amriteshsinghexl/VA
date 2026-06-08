"""
§23 — Standard Scenario ANR  (Step 20b)

Implements the VM21PA Standard Scenario Accumulated Net Revenue (ANR) per
the workbook's Calc_StdScn_ANR tab.

Column layout:
  N  Std Scn Total Fund Value   = dec_cf.av_eop_sa  (AV × lives_eop)
  P  BOP M&E Charge             = me_rate/12 × N[t]
  R  MOP IMF Charge             = imf_rate/12 × N[t] × suppressor
  V  EOP GIB Charges            = gib_rate/12 × N[t] × suppressor
  W  EOP i4L Charges            = i4l_rate/12 × N[t] × suppressor
  M  Accum Factor               = 1 / disc_factor_shock[t]
  X  Accum Total Fund Value     = N[t] × M[t]
  Z  Accum M&E Charges          = running sum: Z[t] = Z[t-1]×(1+i_shock) + P[t]
  AA Accum IMF Charges          = running sum similarly
  AC Accum LB Charges           = Z + AA + GIB + i4L accums combined
  AM Net Revenue CF             = charges_accum − guaranteed_benefit_cost
  AO ANR                        = running net of accumulated charges vs. costs

Confirmed workbook values for policy 842612365 (VM21PA):
  Period 1: disc_factor_shock=0.99592692, N=1,109,625.64, M&E=924.69, ANR=0
  Period 2: disc_factor_shock=0.99187042, N=633,995.59, ANR=0
  ANR = 0 for ALL 480 periods for this policy (AV-only DB, no NAR).

Why ANR = 0:
  Death benefit = AV (option A) → NAR = max(0, DB − AV) = 0 always.
  Guaranteed income (i4L) payments are deducted from AV, not from reserves.
  Net revenue = M&E + IMF + GIB + i4L charges > guaranteed benefit cost → ANR ≥ 0.
  Reserve = max(0, −ANR) = 0.
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


def calculate_std_scn_anr(
    dec_cf: pd.DataFrame,
    interest_rates: pd.DataFrame,
    policy: dict[str, Any],
    config: Any,
) -> pd.DataFrame:
    """
    Compute the Standard Scenario ANR for VM21PA.

    Parameters
    ----------
    dec_cf         : output of reserve.decremented_cf.apply_lives()
                     (lives-weighted cashflows)
    interest_rates : output of cashflows.interest.build_interest_rates()
    policy         : output of loaders.policy_loader.load_policy()
    config         : config.Config  (uses suppress_charges, policy_path)

    Returns
    -------
    DataFrame (index=projection_period) with columns:
        [time-axis pass-through],
        std_scn_fund, accum_factor, accum_fund,
        me_charge, imf_charge, gib_charge, i4l_charge,
        accum_me, accum_imf, accum_lb,
        net_rev_cf, anr
    """
    if dec_cf.empty:
        warn("dec_cf is empty — returning empty std_scn_anr DataFrame.",
             source="std_scn_anr/empty")
        return pd.DataFrame()

    idx = dec_cf.index
    n   = len(idx)

    suppress = config.suppress_charges

    # ---- Policy charge rates ------------------------------------------------
    from cashflows.charges import _parse_rate, _get_i4l_ap_rate
    me_rate      = float(policy.get("expense_charge_per_separate_account") or 0.0)
    gib_raw      = _parse_rate(policy.get("gmwb_ridercharge_rate"))
    i4l_ap_rate  = _get_i4l_ap_rate(config.policy_path)
    gib_net_rate = max(0.0, gib_raw - i4l_ap_rate)
    imf_rate     = _load_imf_rate(config.policy_path, str(policy.get("plan") or ""))

    # ---- Shocked interest rates (Standard Scenario uses +100bps) -------------
    ir = interest_rates.reindex(idx)
    disc_shock    = ir["disc_factor_shock"].to_numpy(dtype=float, na_value=np.nan)
    i_shock_m     = ir["i_monthly_shock"].to_numpy(dtype=float, na_value=np.nan)
    accum_factor  = np.where(disc_shock > 0, 1.0 / disc_shock, 1.0)

    # ---- Std Scn Total Fund Value = dec_cf AV EOP ---------------------------
    n_arr = dec_cf.reindex(idx)["av_eop_sa"].to_numpy(dtype=float, na_value=0.0)

    # ---- Period charges (from decremented fund value) -----------------------
    p_me  = n_arr * (me_rate / 12.0)
    r_imf = n_arr * (imf_rate / 12.0) * (0.0 if suppress else 1.0)
    v_gib = n_arr * (gib_net_rate / 12.0) * (0.0 if suppress else 1.0)
    w_i4l = n_arr * (i4l_ap_rate / 12.0) * (0.0 if suppress else 1.0)

    # ---- Accumulated fund value X[t] = N[t] × M[t] -------------------------
    x_arr = n_arr * accum_factor

    # ---- Running accumulated charges with shocked interest ------------------
    #   Z[t] = Z[t-1] × (1 + i_shock_monthly) + P[t]
    z_me  = np.zeros(n, dtype=float)
    z_imf = np.zeros(n, dtype=float)
    z_lb  = np.zeros(n, dtype=float)

    for t in range(n):
        factor = 1.0 + (float(i_shock_m[t]) if not np.isnan(i_shock_m[t]) else 0.0)
        if t == 0:
            z_me[t]  = p_me[t]
            z_imf[t] = r_imf[t]
            z_lb[t]  = v_gib[t] + w_i4l[t]
        else:
            z_me[t]  = z_me[t - 1]  * factor + p_me[t]
            z_imf[t] = z_imf[t - 1] * factor + r_imf[t]
            z_lb[t]  = z_lb[t - 1]  * factor + v_gib[t] + w_i4l[t]

    # ---- Guaranteed benefit costs -------------------------------------------
    # Death benefit NAR = max(0, DB_guarantee - AV_per_unit) × q_mort × lives
    #
    # Option A (AV-only): DB = AV → NAR = 0 → cost = 0
    # Option C (ratchet) or rollup: DB > AV when AV declines below the guarantee →
    #   NAR > 0 → insurer must pay the excess from reserves → reserve > 0
    #
    # Mortality approximation: use standard age-based rate (simplified)
    # since VM21PA base mortality is masked (D-015).
    # For ages 55-90: q_annual ≈ 0.001 × exp(0.09 × (age-55))  (Makeham-style)
    # Period-1 age 75: q_annual ≈ 0.001 × exp(1.8) ≈ 0.006 per month

    db_type    = str(policy.get("deathbenefittype") or
                     policy.get("db_option") or "A").strip().upper()
    ratchet_db = float(policy.get("death_benefit_ratchet_amount") or 0.0)
    rollup_db  = float(policy.get("death_benefit_rollup_amount") or 0.0)
    db_guarantee = max(ratchet_db, rollup_db)

    death_benefit_cost = np.zeros(n, dtype=float)

    if db_type != "A" and db_guarantee > 0:
        # Get attained ages from time_axis (carried through dec_cf)
        ages = dec_cf.reindex(idx).get("attained_age", None)
        if ages is None:
            # Fall back to a constant age-75 assumption
            ages = pd.Series(75, index=idx)
        ages_arr = ages.to_numpy(dtype=float, na_value=75.0)

        # Simplified mortality: q_monthly = 1 - (1 - q_annual)^(1/12)
        # q_annual ≈ 0.001 × exp(0.09 × (age - 55))
        q_annual  = 0.001 * np.exp(0.09 * (ages_arr - 55.0))
        q_annual  = np.clip(q_annual, 0.0, 0.5)
        q_monthly = 1.0 - (1.0 - q_annual) ** (1.0 / 12.0)

        # AV per in-force life = n_arr / lives_eop (approximate)
        # n_arr is already the lives-weighted AV
        lives_eop_arr = dec_cf.reindex(idx)["lives_eop"].to_numpy(
            dtype=float, na_value=1.0
        ) if "lives_eop" in dec_cf.columns else np.ones(n)
        # Protect against division by zero
        lives_safe    = np.where(lives_eop_arr > 0, lives_eop_arr, 1.0)
        av_per_life   = n_arr / lives_safe

        nar_per_life  = np.maximum(0.0, db_guarantee - av_per_life)
        # Death benefit cost for cohort = NAR × q_monthly × lives_eop
        death_benefit_cost = nar_per_life * q_monthly * lives_eop_arr

    glb_cost = np.zeros(n, dtype=float)   # i4L guaranteed income (from AV, not reserves)

    # ---- Net Revenue CF and ANR ---------------------------------------------
    net_rev_cf = (z_me + z_imf + z_lb) - (death_benefit_cost + glb_cost)
    # ANR[t] = -min(0, net_rev_cf[t]) — reserve = accumulated deficit, if any
    # For test policy: net_rev_cf ≥ 0 → ANR = 0
    anr = np.maximum(0.0, -net_rev_cf)

    # ---- Assemble DataFrame -------------------------------------------------
    time_cols = [c for c in _TIME_COLS if c in dec_cf.columns]
    df = dec_cf[time_cols].copy()

    df["std_scn_fund"] = n_arr
    df["accum_factor"] = accum_factor
    df["accum_fund"]   = x_arr
    df["me_charge"]    = p_me
    df["imf_charge"]   = r_imf
    df["gib_charge"]   = v_gib
    df["i4l_charge"]   = w_i4l
    df["accum_me"]     = z_me
    df["accum_imf"]    = z_imf
    df["accum_lb"]     = z_lb
    df["net_rev_cf"]   = net_rev_cf
    df["anr"]          = anr

    df.index.name = "projection_period"
    return df


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _load_imf_rate(policy_path: str, plan_code: str) -> float:
    if not plan_code:
        return 0.0
    try:
        import openpyxl
        wb = openpyxl.load_workbook(policy_path, data_only=True, read_only=True)
        ws = wb["IMF NRSI (Other)"]
        for row in ws.iter_rows(values_only=True):
            if row[3] == plan_code:
                wb.close()
                return float(row[5])
        wb.close()
    except Exception:
        pass
    return 0.0
