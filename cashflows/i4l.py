"""
Â§17 â€” Abc_corp Income for Life (i4L) Rider Engine  (Step 14)

Implements Calc_i4L â€” the 45-column engine that drives annuity factor pricing,
charges, and guaranteed payment amounts for the i4L lifetime income benefit.

Gate:  ALL output is zero when i4l_indicator != 'i4L'.
4Later sub-branch (B4=1) is inactive for the test policy and stubbed at zero.

Column layout (mirrors Calc_i4L):
  A-H  : time spine (pass-through from time_axis)
  I    : 4later_ap_flag         (always 0 for non-4Later)
  M, N, O, P : AP timing        (computed from policy parameters)
  R, S, T    : i4L mortality     (R=annual, S=monthly UDD, T=survivorship)
  U          : discount factor   (AIR recurrence, seed=1)
  V          : AP annuity factor         (sum of U over AP window / 12)
  W          : post-AP annuity factor    (sum of TÃ—U post-AP / 12 / adjustments)
  Y, Z       : 4Later CIB start / cap    (stub = 0, B4 inactive)
  AA, AB     : 4Later CIB end / cap end  (stub = 0)
  AD         : 4Later charge             (stub = 0)
  AE         : GIB charge                (stub = 0; needs AV â€” filled by cashflow engine)
  AF         : i4L charge                (stub = 0; needs AV)
  AG         : policy load               (stub = 0; 4Later only)
  AH         : one-time AP-end load      (stub = 0; needs AV)
  AI         : current payment          (stub = 0; needs AV + V + W)
  AQ         : monthly payment          (stub = 0)
  AN         : min payment floor        (stub = 0)
  AR, AS     : COI factor / COI credit  (stub = 0)

Stubs pending cashflow-engine integration (Step 19):
  All AV-dependent columns (AE, AF, AH, AI, AQ, AN, AR, AS) are set to 0.0
  until the integrated loop in cashflow_engine.py provides the total AV series.

Mortality (R, S, T):
  Uses All_i4L_MortalityTables from Assumptions_Extracted.xlsx.
  SOURCE: Assumptions!$BWK$7:$BWS$~  (tilde = truncated extraction, D-009).
  In the sandbox workbook the table was extracted incompletely (D-016); the
  Python fallback returns NaN for R/S/T with a ModelWarning.

Discount factor (U):
  Seed U[1] = 1.  Recurrence: U[t] = U[t-1] / (1 + AIR)^(1/12)
  where AIR = policy['i4l_assumed_investment_return'].
  NOTE: Uses EFFECTIVE annual compounding (1+AIR)^(1/12), NOT simple monthly
  (1 + AIR/12) â€” the workbook uses Policy_Info!C88 as an annual effective rate.

AP Annuity Factor (V):
  V[t] = sum(U[t:t+O[t]]) / U[t] / 12
  = Ã¤_{O[t]} at monthly effective rate (1+AIR)^(1/12) âˆ’ 1.
  No mortality in V (access-period payments are guaranteed regardless of survival).

Post-AP Annuity Factor (W):
  When O[t] > 0 (within AP):
    W[t] = sum(T[t+O:N]Ã—U[t+O:N]) / (T[t+O] Ã— U[t] Ã— 12)
           / (1 âˆ’ AdjLoad) / (1 âˆ’ PremTax)
  When O[t] â‰¤ 0 (post-AP):
    W[t] = sum(T[t:N]Ã—U[t:N]) / T[t] / U[t] / 12

Key workbook-verified values (policy 842612365, VM21PA):
  Period 1: R=0.573084, S=0.068474, T=1.0, U=1.0,
            V=11.357842388, W=0.494584812 (O=180, AIR=4%)
  Period 2: T=0.931526455, U=0.996736943, V=11.311418863
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
from typing import Any

from loaders.warnings import warn

_TIME_COLS = [
    "policy_year", "policy_month", "month_in_policy_year",
    "bop_date", "eop_date", "cal_month_end", "attained_age",
]

# GIB rate net of i4L AP rate: B3 = GIB_product_rate âˆ’ B1
# For plan LMFR5: 0.009 (from gmwb_ridercharge_rate) âˆ’ 0.005 (i4l_expense_load) = 0.004
# B1 = i4l_expense_load  (during AP)
# B3 = gib_gross âˆ’ B1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_i4l(
    time_axis: pd.DataFrame,
    policy: dict[str, Any],
    assumptions: dict[str, pd.DataFrame],
    config: Any,
) -> pd.DataFrame:
    """
    Build the Calc_i4L engine output for one policy.

    Parameters
    ----------
    time_axis   : output of decrements.time_axis.build_time_axis()
    policy      : output of loaders.policy_loader.load_policy()
    assumptions : output of loaders.assumption_loader.load_assumptions()
    config      : config.Config instance

    Returns
    -------
    DataFrame (index=projection_period) with 31 data columns (see module docstring).
    All columns are zero when i4l_indicator != 'i4L'.
    """
    if time_axis.empty:
        warn("time_axis is empty â€” returning empty i4l DataFrame.",
             source="i4l/empty_time_axis")
        return pd.DataFrame()

    indicator = str(policy.get("i4l_indicator") or "").strip()
    if indicator != "i4L":
        return _build_zero_i4l(time_axis)

    return _build_active_i4l(time_axis, policy, assumptions, config)


# ---------------------------------------------------------------------------
# Active i4L path
# ---------------------------------------------------------------------------

def _build_active_i4l(
    time_axis: pd.DataFrame,
    policy: dict[str, Any],
    assumptions: dict[str, pd.DataFrame],
    config: Any,
) -> pd.DataFrame:
    idx  = time_axis.index
    n    = len(idx)

    # ---- policy parameters ---------------------------------------------------
    air        = float(policy.get("i4l_assumed_investment_return") or 0.04)
    access_yrs = int(policy.get("i4l_access_period_pa") or 15)
    deferral   = int(policy.get("i4l_deferral_months") or 0)
    adj_load   = float(policy.get("i4l_expense_load") or 0.0)
    prem_tax   = float(policy.get("i4l_premium_tax") or 0.0)
    issue_age  = int(policy.get("issue_age") or 0)
    mort_tbl   = str(policy.get("i4l_mortality_table") or "Qi4LTbl1").strip()
    gender     = str(policy.get("gender1") or policy.get("gender") or "M").strip()

    # GIB charge rate = raw rider charge âˆ’ i4L AP expense rate
    gib_raw       = _parse_rate_semicolon(policy.get("gmwb_ridercharge_rate"))
    i4l_ap_rate   = float(policy.get("i4l_expense_load") or 0.005)  # B1
    gib_net_rate  = max(0.0, gib_raw - i4l_ap_rate)                  # B3

    # ---- AP timing -----------------------------------------------------------
    pol_months = time_axis["policy_month"].to_numpy(dtype=int)

    m_pmt_start  = deferral + 1               # Pol Month Pmt Start (constant)
    access_months = access_yrs * 12
    n_ap_date_idx = m_pmt_start + access_months - 1   # AP Date Index (constant)
    p_ap_end_age  = n_ap_date_idx // 12 + issue_age   # AP End Age (constant)

    o_ap_remaining = n_ap_date_idx - pol_months       # changes each period

    # ---- discount factor U ---------------------------------------------------
    u_arr = _build_disc_factor(n, air)

    # ---- mortality: R, S, T --------------------------------------------------
    age_shift = _get_age_shift(assumptions, policy)
    r_arr, s_arr, t_arr = _build_mortality(
        time_axis, assumptions, mort_tbl, gender, age_shift
    )

    # ---- AP annuity factor V (purely interest-based, no mortality) -----------
    v_arr = _build_v_factor(u_arr, o_ap_remaining, n)

    # ---- post-AP annuity factor W (life-contingent) -------------------------
    w_arr = _build_w_factor(u_arr, t_arr, o_ap_remaining, n, adj_load, prem_tax)

    # ---- assemble DataFrame --------------------------------------------------
    time_cols = [c for c in _TIME_COLS if c in time_axis.columns]
    df = time_axis[time_cols].copy()

    # AP timing
    df["m_pmt_start"]    = m_pmt_start
    df["n_ap_date_idx"]  = n_ap_date_idx
    df["o_ap_remaining"] = o_ap_remaining
    df["p_ap_end_age"]   = p_ap_end_age

    # Mortality / survival / discount
    df["r_annual_mort"]  = r_arr
    df["s_monthly_mort"] = s_arr
    df["t_survivorship"] = t_arr
    df["u_disc_factor"]  = u_arr

    # Annuity factors
    df["v_ap_annuity"]     = v_arr
    df["w_postap_annuity"] = w_arr

    # 4Later CIB (inactive for non-4Later policies)
    for col in ("cib_start", "cib_cap_start", "cib_end", "cib_cap_end"):
        df[col] = 0.0

    # Stub columns (AV-dependent â€” filled by cashflow engine in Step 19)
    for col in ("charge_4later", "charge_gib", "charge_i4l",
                "policy_load", "oneoff_ap_load",
                "current_payment", "monthly_payment", "min_payment",
                "coi_factor", "coi_credit"):
        df[col] = 0.0

    df.index.name = "projection_period"
    return df


# ---------------------------------------------------------------------------
# Discount factor
# ---------------------------------------------------------------------------

def _build_disc_factor(n: int, air: float) -> np.ndarray:
    """
    U[1] = 1.0 (seed)
    U[t] = U[t-1] / (1 + AIR)^(1/12)   â€” effective annual compounding
    """
    monthly_divisor = (1.0 + air) ** (1.0 / 12.0)
    u = np.empty(n, dtype=float)
    u[0] = 1.0
    for t in range(1, n):
        u[t] = u[t - 1] / monthly_divisor
    return u


# ---------------------------------------------------------------------------
# AP annuity factor (V)
# ---------------------------------------------------------------------------

def _build_v_factor(
    u_arr: np.ndarray,
    o_arr: np.ndarray,
    n: int,
) -> np.ndarray:
    """
    V[t] = sum(U[t : t+O[t]]) / U[t] / 12   when O[t] > 0, else 0.

    This is Ã¤_{O[t]} at monthly effective rate (1+AIR)^(1/12)âˆ’1, divided by 12
    to express as an annual-payment annuity factor.

    No mortality in V â€” access-period payments are guaranteed regardless of survival.
    """
    v = np.zeros(n, dtype=float)
    for t in range(n):
        o = int(o_arr[t])
        if o <= 0:
            continue
        end = min(t + o, n)          # don't exceed projection length
        sum_u = np.sum(u_arr[t:end])
        v[t] = sum_u / u_arr[t] / 12.0
    return v


# ---------------------------------------------------------------------------
# Post-AP annuity factor (W)
# ---------------------------------------------------------------------------

def _build_w_factor(
    u_arr: np.ndarray,
    t_arr: np.ndarray,
    o_arr: np.ndarray,
    n: int,
    adj_load: float,
    prem_tax: float,
) -> np.ndarray:
    """
    When O[t] > 0 (within AP):
      W[t] = [sum(T[t+O:N] Ã— U[t+O:N]) / (T[t+O] Ã— U[t] Ã— 12)]
             / (1 âˆ’ PremTax) / (1 âˆ’ AdjLoad)

    When O[t] â‰¤ 0 (post-AP):
      W[t] = sum(T[t:N] Ã— U[t:N]) / T[t] / U[t] / 12

    Returns NaN whenever T contains NaN (mortality table not available).
    """
    load_adj = (1.0 - prem_tax) * (1.0 - adj_load)
    w = np.zeros(n, dtype=float)

    for t in range(n):
        o = int(o_arr[t])
        ut = u_arr[t]
        tt = t_arr[t]

        if np.isnan(tt) or np.isnan(ut) or ut == 0.0:
            w[t] = np.nan
            continue

        if o > 0:
            ap_end = min(t + o, n)
            if ap_end >= n:
                w[t] = 0.0
                continue
            t_ap  = t_arr[ap_end]
            if np.isnan(t_ap) or t_ap == 0.0:
                w[t] = np.nan
                continue
            tu_sum = np.nansum(t_arr[ap_end:n] * u_arr[ap_end:n])
            # Check if any NaN in the slice
            if np.any(np.isnan(t_arr[ap_end:n]) | np.isnan(u_arr[ap_end:n])):
                w[t] = np.nan
                continue
            w[t] = (tu_sum / (t_ap * ut * 12.0)) / load_adj
        else:
            # post-AP: pure whole-life annuity from t onward
            if np.isnan(tt) or tt == 0.0:
                w[t] = np.nan
                continue
            if np.any(np.isnan(t_arr[t:n]) | np.isnan(u_arr[t:n])):
                w[t] = np.nan
                continue
            tu_sum = np.sum(t_arr[t:n] * u_arr[t:n])
            w[t] = tu_sum / (tt * ut * 12.0)

    return w


# ---------------------------------------------------------------------------
# Mortality: R, S, T
# ---------------------------------------------------------------------------

def _build_mortality(
    time_axis: pd.DataFrame,
    assumptions: dict[str, pd.DataFrame],
    mort_tbl: str,
    gender: str,
    age_shift: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Look up annual mortality R from All_i4L_MortalityTables.

    Table structure: attained-age rows Ã— 9 columns
      Qi4LTbl1/M, Qi4LTbl1/F, Qi4LTbl1/U,
      Qi4LTbl2/M, ...  Qi4LTbl3/U
    Values are stored as per-mille (divide by 1000 â†’ decimal).

    D-016: All_i4L_MortalityTables is truncated in Assumptions_Extracted.xlsx
    (source range ends with ~). Returns NaN with ModelWarning.
    """
    tbl = assumptions.get("All_i4L_MortalityTables")
    n = len(time_axis)

    r_arr = np.full(n, np.nan)

    if tbl is None or tbl.empty or len(tbl) < 2:
        warn(
            "All_i4L_MortalityTables is absent or truncated in "
            "Assumptions_Extracted.xlsx (D-016). "
            "i4L mortality (R, S, T[1:]) and W annuity factor will be NaN. "
            "T[1]=1.0 seed is preserved. "
            "Populate from live Assumptions!$BWK$7:$BWS tab before production use.",
            source="i4l/mortality_table_missing",
        )
        nan_arr = np.full(n, np.nan)
        t_arr   = np.full(n, np.nan)
        t_arr[0] = 1.0              # seed is always 1.0 (T[period 1] = 1)
        return nan_arr, nan_arr, t_arr

    # Determine column label: "{mort_tbl}/{gender}"
    col_label = f"{mort_tbl}/{gender}"
    if col_label not in tbl.columns:
        # Try just gender
        if gender in tbl.columns:
            col_label = gender
        else:
            warn(
                f"All_i4L_MortalityTables: column '{col_label}' not found. "
                f"Available: {list(tbl.columns)}. Mortality will be NaN.",
                source="i4l/mortality_col_not_found",
            )
            nan_arr = np.full(n, np.nan)
            return nan_arr, nan_arr, nan_arr

    attained_ages = time_axis["attained_age"].to_numpy(dtype=int)

    for t, age in enumerate(attained_ages):
        lookup_age = age + age_shift
        try:
            r_arr[t] = float(tbl.iloc[lookup_age][col_label]) / 1000.0
        except (IndexError, KeyError, TypeError, ValueError):
            r_arr[t] = np.nan

    # Monthly UDD: S = 1 - (1-R)^(1/12)
    s_arr = 1.0 - (1.0 - r_arr) ** (1.0 / 12.0)

    # Survivorship: T[0]=1, T[t] = T[t-1] Ã— (1-S[t-1])
    t_surv = np.empty(n, dtype=float)
    t_surv[0] = 1.0
    for t in range(1, n):
        prev = t_surv[t - 1]
        s_prev = s_arr[t - 1]
        if np.isnan(prev) or np.isnan(s_prev):
            t_surv[t] = np.nan
        else:
            t_surv[t] = prev * (1.0 - s_prev)

    return r_arr, s_arr, t_surv


# ---------------------------------------------------------------------------
# Age shift lookup
# ---------------------------------------------------------------------------

def _get_age_shift(
    assumptions: dict[str, pd.DataFrame],
    policy: dict[str, Any],
) -> int:
    """
    Look up i4L mortality age shift from All_i4L_MortalityAgeShift.

    Key = IssueYear âˆ’ IssueAge (approximate birth decade).
    Returns 0 if table is unavailable (D-016).

    Confirmed: IssueYear=2007, IssueAge=58 â†’ key=1949 â†’ shift=2 for test policy.
    """
    tbl = assumptions.get("All_i4L_MortalityAgeShift")
    if tbl is None or tbl.empty:
        warn(
            "All_i4L_MortalityAgeShift is absent or empty in "
            "Assumptions_Extracted.xlsx (D-016). Using age shift = 0.",
            source="i4l/age_shift_table_missing",
        )
        return 0

    try:
        issue_year = int(policy.get("issue_year") or 0)
        issue_age  = int(policy.get("issue_age") or 0)
        key = issue_year - issue_age   # approximate birth year
        data_cols = [c for c in tbl.columns if c != "src_row"]
        if not data_cols:
            return 0
        # Table: first col = birth decade key, second col = age shift
        # Find nearest decade
        for i in range(len(tbl)):
            row = tbl.iloc[i]
            if int(row[data_cols[0]]) <= key:
                if len(data_cols) > 1:
                    return int(row[data_cols[1]])
        return 0
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Zero i4L (non-i4L policies)
# ---------------------------------------------------------------------------

def _build_zero_i4l(time_axis: pd.DataFrame) -> pd.DataFrame:
    """Return all-zero i4l DataFrame for non-i4L policies."""
    time_cols = [c for c in _TIME_COLS if c in time_axis.columns]
    df = time_axis[time_cols].copy()
    for col in (
        "m_pmt_start", "n_ap_date_idx", "o_ap_remaining", "p_ap_end_age",
        "r_annual_mort", "s_monthly_mort", "t_survivorship", "u_disc_factor",
        "v_ap_annuity", "w_postap_annuity",
        "cib_start", "cib_cap_start", "cib_end", "cib_cap_end",
        "charge_4later", "charge_gib", "charge_i4l", "policy_load", "oneoff_ap_load",
        "current_payment", "monthly_payment", "min_payment",
        "coi_factor", "coi_credit",
    ):
        df[col] = 0.0
    df.index.name = "projection_period"
    return df


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _parse_rate_semicolon(raw) -> float:
    """
    Parse a rate field that may contain a semicolon-delimited string,
    e.g. '0.009000;10/23/2063'. Returns the first numeric value.
    """
    if raw is None:
        return 0.0
    s = str(raw).strip()
    if ";" in s:
        s = s.split(";")[0].strip()
    try:
        return float(s)
    except ValueError:
        return 0.0
