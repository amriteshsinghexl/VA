"""
Excel formula registry for VA model output sheets.

Each ColFormula entry describes how a column is derived as an Excel formula
template.  Placeholders:

    [col_name]       → same row, column named col_name (e.g. B3)
    [prev:col_name]  → previous row of col_name        (e.g. B2 when writing row 3)
    [last:col_name]  → last data row of col_name        (e.g. B481 for 480-row sheet)

The writer (`output/writer.py`) resolves placeholders at write time so every
data cell carries a live Excel formula.  Clicking any cell in Excel reveals the
full derivation chain.

Build the registry with::

    from output.formula_registry import build_registry
    reg = build_registry(policy, config)   # {sheet_name: {col_name: ColFormula}}
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ColFormula:
    """Formula descriptor for one output column."""
    # Excel formula template for the first data row (no predecessor available)
    first_row: str
    # Template for rows 2+ of data (may use [prev:col_name] back-references).
    # Defaults to first_row when the formula is the same for every row.
    rest_rows: str = ""
    # Human-readable description — written as an Excel header comment
    description: str = ""
    # Python source file where this formula originates (for traceability)
    source: str = ""

    def __post_init__(self) -> None:
        if not self.rest_rows:
            self.rest_rows = self.first_row

    @property
    def is_recurrent(self) -> bool:
        """True when first_row and rest_rows differ (recurrence relation)."""
        return self.first_row != self.rest_rows


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_registry(
    policy: Dict[str, Any],
    config: Any,
) -> Dict[str, Dict[str, ColFormula]]:
    """
    Build the complete formula registry with policy constants embedded.

    Parameters
    ----------
    policy : dict from loaders.policy_loader.load_policy()
    config : config.Config

    Returns
    -------
    {sheet_name: {col_name: ColFormula}}
    """
    # ---- Resolve policy constants -------------------------------------------
    me_rate      = float(policy.get("expense_charge_per_separate_account") or 0.0)
    plan_code    = str(policy.get("plan") or policy.get("model_plan") or "")
    suppressor   = 0.0 if config.suppress_charges else 1.0
    air          = float(policy.get("i4l_assumed_investment_return") or 0.04)
    adj_load     = float(policy.get("i4l_expense_load") or 0.03)
    prem_tax     = float(policy.get("i4l_premium_tax") or 0.005)

    try:
        from cashflows.charges import _parse_rate, _get_i4l_ap_rate
        gib_raw      = _parse_rate(policy.get("gmwb_ridercharge_rate"))
        i4l_ap_rate  = _get_i4l_ap_rate(config.policy_path)
    except Exception:
        gib_raw     = 0.0
        i4l_ap_rate = 0.0

    gib_net_rate = max(0.0, gib_raw - i4l_ap_rate)
    imf_rate     = _load_imf_rate(config.policy_path, plan_code)

    # Short string representations of per-month rates for formula text
    def _r(v: float) -> str:
        return f"{v:.8f}"

    sup_str = f"{suppressor:.1f}"

    reg: Dict[str, Dict[str, ColFormula]] = {}

    # ======================================================================
    # 02_Mortality
    # ======================================================================
    reg["02_Mortality"] = {
        "q_monthly": ColFormula(
            first_row="=1 - (1 - [q_annual])^(1/12)",
            description="Monthly UDD mortality rate: 1-(1-q_annual)^(1/12)",
            source="decrements/mortality.py",
        ),
    }

    # ======================================================================
    # 03_Lapse
    # ======================================================================
    reg["03_Lapse"] = {
        "q_lapse_monthly": ColFormula(
            first_row="=1 - (1 - [q_lapse_annual])^(1/12)",
            description="Monthly lapse rate: 1-(1-q_annual)^(1/12)",
            source="decrements/lapse.py",
        ),
    }

    # ======================================================================
    # 04_Lives
    # ======================================================================
    reg["04_Lives"] = {
        "lives_bop": ColFormula(
            first_row="=1",
            rest_rows="=[prev:lives_eop]",
            description="Lives at BOP: seed=1.0; lives_bop[t]=lives_eop[t-1]",
            source="decrements/lives.py",
        ),
        "lives_eop": ColFormula(
            first_row="=[lives_bop] * (1 - [q_mort_monthly]) * (1 - [q_lapse_monthly])",
            description="Lives at EOP: BOP × (1-q_mort) × (1-q_lapse)",
            source="decrements/lives.py",
        ),
    }

    # ======================================================================
    # 05_Interest_Rates
    # ======================================================================
    reg["05_Interest_Rates"] = {
        "i_aey": ColFormula(
            first_row="=(1 + [i_bey_pct] / 100 / 2)^2 - 1",
            description="Annual Effective Yield: (1+BEY/2)^2-1  (semi-annual BEY conversion)",
            source="cashflows/interest.py",
        ),
        "i_monthly": ColFormula(
            first_row="=(1 + [i_aey])^(1/12) - 1",
            description="Monthly effective rate: (1+AEY)^(1/12)-1",
            source="cashflows/interest.py",
        ),
        "disc_factor": ColFormula(
            first_row="=1 / (1 + [i_monthly])",
            rest_rows="=[prev:disc_factor] / (1 + [i_monthly])",
            description="Running discount factor: df[t]=df[t-1]/(1+i_monthly[t]); seed=1.0",
            source="cashflows/interest.py",
        ),
        "i_aey_shock": ColFormula(
            first_row="=[i_aey] + 0.01",
            description="Shocked AEY = AEY + 100bps (VM21PA Standard Scenario)",
            source="cashflows/interest.py",
        ),
        "i_monthly_shock": ColFormula(
            first_row="=(1 + [i_aey_shock])^(1/12) - 1",
            description="Monthly effective rate for +100bps shocked scenario",
            source="cashflows/interest.py",
        ),
        "disc_factor_shock": ColFormula(
            first_row="=1 / (1 + [i_monthly_shock])",
            rest_rows="=[prev:disc_factor_shock] / (1 + [i_monthly_shock])",
            description="Running discount factor for shocked (+100bps) rates",
            source="cashflows/interest.py",
        ),
    }

    # ======================================================================
    # 06_Fund_Mechanics
    # Each fund k: growth_fk = (1 + r_annual_k)^(1/12) - 1
    # ======================================================================
    reg["06_Fund_Mechanics"] = {}
    for k in range(1, 7):
        reg["06_Fund_Mechanics"][f"growth_f{k}"] = ColFormula(
            first_row=f"=(1 + ([eq_growth_f{k}] + [eq_income_f{k}]) / 100)^(1/12) - 1",
            description=f"Fund {k} monthly growth factor: (1+r_annual)^(1/12)-1",
            source="cashflows/fund_mechanics.py",
        )

    # ======================================================================
    # 09_Cashflow_Engine
    # ======================================================================
    reg["09_Cashflow_Engine"] = {
        "me_sa": ColFormula(
            first_row=f"=[av_bop_sa] * ({_r(me_rate)} / 12)",
            description=f"M&E charge = BOP_AV × me_rate/12  (me_rate={me_rate:.6f})",
            source="cashflows/cashflow_engine.py",
        ),
        "imf_sa": ColFormula(
            first_row=f"=([av_bop_sa] - [me_sa]) * ({_r(imf_rate)} / 12) * {sup_str}",
            description=f"IMF charge = (BOP-ME) × imf_rate/12 × suppressor  (imf_rate={imf_rate:.6f}, suppressor={suppressor})",
            source="cashflows/cashflow_engine.py",
        ),
        "av_at_cme_sa": ColFormula(
            first_row="=([av_bop_sa] - [me_sa]) - [imf_sa] + [growth_sa]",
            description="AV at charge-moment-end: (BOP-ME) - IMF + Growth",
            source="cashflows/cashflow_engine.py",
        ),
        "gib_charge": ColFormula(
            first_row=f"=[av_at_cme_sa] * ({_r(gib_net_rate)} / 12) * {sup_str}",
            description=f"GIB net charge = at-CME_AV × gib_net_rate/12  (gib_net_rate={gib_net_rate:.6f})",
            source="cashflows/cashflow_engine.py",
        ),
        "i4l_charge": ColFormula(
            first_row=f"=[av_at_cme_sa] * ({_r(i4l_ap_rate)} / 12) * {sup_str}",
            description=f"i4L charge = at-CME_AV × i4l_ap_rate/12  (i4l_ap_rate={i4l_ap_rate:.6f})",
            source="cashflows/cashflow_engine.py",
        ),
        "withdrawal": ColFormula(
            first_row="=[monthly_payment]",
            description="Guaranteed income withdrawal = monthly_payment",
            source="cashflows/cashflow_engine.py",
        ),
        "av_eop_sa": ColFormula(
            first_row="=MAX(0, [av_at_cme_sa] - [gib_charge] - [i4l_charge] - [withdrawal])",
            description="AV at EOP: MAX(0, at-CME - GIB - i4L - withdrawal)",
            source="cashflows/cashflow_engine.py",
        ),
        "monthly_payment": ColFormula(
            first_row="=[current_payment] / 12",
            description="Monthly guaranteed income payment = annual_payment / 12",
            source="cashflows/cashflow_engine.py",
        ),
        "av_bop_total": ColFormula(
            first_row="=[av_bop_sa]",
            description="Total BOP AV = SA AV (fixed account = 0 for this policy)",
            source="cashflows/cashflow_engine.py",
        ),
        "av_eop_total": ColFormula(
            first_row="=[av_eop_sa]",
            description="Total EOP AV = SA AV (fixed account = 0 for this policy)",
            source="cashflows/cashflow_engine.py",
        ),
    }

    # ======================================================================
    # 10_Dec_Cashflows  — each numeric col = cashflow_col × lives_eop
    # ======================================================================
    _DEC_CF_NUMERIC_COLS = [
        "av_bop_sa", "me_sa", "imf_sa", "growth_sa", "av_at_cme_sa",
        "gib_charge", "i4l_charge", "withdrawal", "av_eop_sa",
        "current_payment", "monthly_payment",
        "av_bop_total", "av_eop_total",
    ] + [f"av_eop_f{k}" for k in range(1, 7)]

    reg["10_Dec_Cashflows"] = {
        col: ColFormula(
            first_row=f"=[{col}] * [lives_eop]",
            description=f"Decremented: per-unit {col} × lives_eop",
            source="reserve/decremented_cf.py",
        )
        for col in _DEC_CF_NUMERIC_COLS
    }

    # ======================================================================
    # 11_StdScn_ANR
    # Recurrent accumulated charge formulas use accum_factor to back out
    # the shocked monthly rate: (1+i_shock_m) = accum_factor[t]/accum_factor[t-1]
    # ======================================================================
    reg["11_StdScn_ANR"] = {
        "accum_factor": ColFormula(
            first_row="=1 / [disc_factor_shock]",
            description="Accumulation factor M[t] = 1 / disc_factor_shock[t]",
            source="reserve/std_scn_anr.py",
        ),
        "accum_fund": ColFormula(
            first_row="=[std_scn_fund] * [accum_factor]",
            description="Accumulated fund = std_scn_fund × accum_factor",
            source="reserve/std_scn_anr.py",
        ),
        "me_charge": ColFormula(
            first_row=f"=[std_scn_fund] * ({_r(me_rate)} / 12)",
            description=f"M&E charge on decremented fund  (me_rate={me_rate:.6f})",
            source="reserve/std_scn_anr.py",
        ),
        "imf_charge": ColFormula(
            first_row=f"=[std_scn_fund] * ({_r(imf_rate)} / 12) * {sup_str}",
            description=f"IMF charge on decremented fund  (imf_rate={imf_rate:.6f})",
            source="reserve/std_scn_anr.py",
        ),
        "gib_charge": ColFormula(
            first_row=f"=[std_scn_fund] * ({_r(gib_net_rate)} / 12) * {sup_str}",
            description=f"GIB charge on decremented fund  (gib_net_rate={gib_net_rate:.6f})",
            source="reserve/std_scn_anr.py",
        ),
        "i4l_charge": ColFormula(
            first_row=f"=[std_scn_fund] * ({_r(i4l_ap_rate)} / 12) * {sup_str}",
            description=f"i4L charge on decremented fund  (i4l_ap_rate={i4l_ap_rate:.6f})",
            source="reserve/std_scn_anr.py",
        ),
        # Recurrence: Z[t] = Z[t-1] × (1+i_shock_m) + charge[t]
        # (1+i_shock_m) = accum_factor[t] / accum_factor[t-1]
        "accum_me": ColFormula(
            first_row="=[me_charge]",
            rest_rows="=[prev:accum_me] * ([accum_factor] / [prev:accum_factor]) + [me_charge]",
            description="Accumulated M&E: Z[t]=Z[t-1]×(1+i_shock)+P[t]",
            source="reserve/std_scn_anr.py",
        ),
        "accum_imf": ColFormula(
            first_row="=[imf_charge]",
            rest_rows="=[prev:accum_imf] * ([accum_factor] / [prev:accum_factor]) + [imf_charge]",
            description="Accumulated IMF: running sum with shocked interest",
            source="reserve/std_scn_anr.py",
        ),
        "accum_lb": ColFormula(
            first_row="=[gib_charge] + [i4l_charge]",
            rest_rows="=[prev:accum_lb] * ([accum_factor] / [prev:accum_factor]) + [gib_charge] + [i4l_charge]",
            description="Accumulated LB charges (GIB+i4L): running sum with shocked interest",
            source="reserve/std_scn_anr.py",
        ),
        "net_rev_cf": ColFormula(
            first_row="=[accum_me] + [accum_imf] + [accum_lb]",
            description="Net Revenue CF = accum_ME + accum_IMF + accum_LB (minus benefit costs; =0 for option-A policy)",
            source="reserve/std_scn_anr.py",
        ),
        "anr": ColFormula(
            first_row="=MAX(0, -[net_rev_cf])",
            description="ANR = MAX(0, -net_rev_cf); reserve required if net revenue is negative",
            source="reserve/std_scn_anr.py",
        ),
    }

    # ======================================================================
    # 12_CARVM
    # carvm_reserve is a backward running-max: MAX(pv_max from t to end).
    # Expressed as MAX([pv_max], [next:carvm_reserve]) — the writer uses
    # the last-row sentinel: MAX([pv_max], 0) for the final period.
    # ======================================================================
    reg["12_CARVM"] = {
        "pv_csv": ColFormula(
            first_row="=[csv_at_me] * [disc_factor]",
            description="PV of CSV: csv_at_me × disc_factor (unshocked rates)",
            source="reserve/carvm.py",
        ),
        "pv_annuity": ColFormula(
            first_row="=0",
            description="PV of annuity benefit (0 for AV-only DB option A)",
            source="reserve/carvm.py",
        ),
        "pv_max": ColFormula(
            first_row="=MAX([pv_csv], [pv_annuity])",
            description="Max PV benefit at period t: MAX(PV_CSV, PV_annuity)",
            source="reserve/carvm.py",
        ),
        "carvm_reserve": ColFormula(
            # Backward running max: last row = pv_max; others = MAX(pv_max, next carvm)
            first_row="=MAX([pv_max], [next:carvm_reserve])",
            rest_rows="=MAX([pv_max], [next:carvm_reserve])",
            description="CARVM reserve = running MAX of pv_max from t to end (backward)",
            source="reserve/carvm.py",
        ),
    }

    # ======================================================================
    # 14_Reserve_Summary
    # ======================================================================
    reg["14_Reserve_Summary"] = {
        "anr": ColFormula(
            first_row="=[anr]",   # pass-through from std_scn
            description="Standard Scenario ANR (from 11_StdScn_ANR)",
            source="reserve/reserve_aggregator.py",
        ),
        "reserve_t0": ColFormula(
            first_row="=MAX(0, [anr])",
            description="Final reserve = MAX(0, ANR) for VM21PA basis",
            source="reserve/reserve_aggregator.py",
        ),
    }

    return reg


# ---------------------------------------------------------------------------
# Helpers used during registry construction
# ---------------------------------------------------------------------------

def _load_imf_rate(policy_path: str, plan_code: str) -> float:
    """Load IMF rate from policy workbook (mirrors cashflow_engine logic)."""
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
