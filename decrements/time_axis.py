"""
§5 / §7 — Time Axis

Builds the 8-column A–H projection spine matching Calc_StdScn_ANR / Calc_CARVM
rows 10 onwards.

Columns:
  A  projection_period       : 1, 2, …, projection_months
  B  policy_year             : (policy_month − 1) // 12 + 1
  C  policy_month            : policy_month_seed + period − 1
  D  month_in_policy_year    : policy_month − (policy_year − 1) * 12
  E  bop_date                : valuation_date for period 1;
                               first of each subsequent calendar month for periods 2+
  F  eop_date                : first day of the calendar month following bop_date
  G  cal_month_end           : last day of bop_date's calendar month
  H  attained_age            : attained_age_seed + (policy_year − initial_policy_year)

All date columns are Python datetime.date objects.

BOP / EOP date rules (observed from Calc_StdScn_ANR):
  • period 1 BOP = valuation_date  (the last calendar day of the valuation month)
  • period t≥2 BOP = first day of (valuation_month + t − 1)
  • eop_date for ALL periods = first day of (bop_month + 1)
  • cal_month_end = last day of bop_date's calendar month

D-011: Workbook Calc_ tabs contain 1200 rows (100 years). Config.projection_months
defaults to 480. Python model uses config.projection_months; the workbook discrepancy
is noted in DISCREPANCIES.md.
"""
from __future__ import annotations

import calendar
import datetime
from typing import Any

import pandas as pd


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_time_axis(policy: dict[str, Any], config: Any) -> pd.DataFrame:
    """
    Build the A–H time-axis DataFrame for one policy.

    Parameters
    ----------
    policy : dict  — output of policy_loader.load_policy()
    config : Config — from config.Config

    Returns
    -------
    DataFrame with columns:
        projection_period, policy_year, policy_month, month_in_policy_year,
        bop_date, eop_date, cal_month_end, attained_age
    Index = projection_period (1..N), dtype int.
    """
    n_months       = config.projection_months
    pms            = policy["policy_month_seed"]     # e.g. 215
    age_seed       = policy["attained_age_seed"]     # e.g. 75
    val_date       = policy["valuation_date"]        # datetime.date last-day of val month

    # Initial policy year (the year number in force at period 1)
    initial_policy_year = (pms - 1) // 12 + 1

    records = []
    for t in range(1, n_months + 1):
        pol_month = pms + t - 1
        pol_year  = (pol_month - 1) // 12 + 1
        mo_in_yr  = pol_month - (pol_year - 1) * 12

        bop = _bop_date(val_date, t)
        eop = _first_of_next_month(bop)
        cal_end = _last_day_of_month(bop.year, bop.month)
        att_age = age_seed + (pol_year - initial_policy_year)

        records.append({
            "projection_period":    t,
            "policy_year":          pol_year,
            "policy_month":         pol_month,
            "month_in_policy_year": mo_in_yr,
            "bop_date":             bop,
            "eop_date":             eop,
            "cal_month_end":        cal_end,
            "attained_age":         att_age,
        })

    df = pd.DataFrame(records).set_index("projection_period")
    df.index.name = "projection_period"
    return df


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _bop_date(valuation_date: datetime.date, period: int) -> datetime.date:
    """
    BOP for projection period t.

    period=1  → valuation_date  (last day of the valuation calendar month)
    period≥2  → first day of calendar month (val_month + t − 1)

    Example: val=2025-06-30, t=2 → 2025-07-01; t=3 → 2025-08-01
    """
    if period == 1:
        return valuation_date
    offset_months = period - 1          # months after valuation month
    base_year  = valuation_date.year
    base_month = valuation_date.month
    total_month = base_month + offset_months
    y = base_year + (total_month - 1) // 12
    m = (total_month - 1) % 12 + 1
    return datetime.date(y, m, 1)


def _first_of_next_month(d: datetime.date) -> datetime.date:
    """Return the first day of the calendar month following d."""
    if d.month == 12:
        return datetime.date(d.year + 1, 1, 1)
    return datetime.date(d.year, d.month + 1, 1)


def _last_day_of_month(year: int, month: int) -> datetime.date:
    last = calendar.monthrange(year, month)[1]
    return datetime.date(year, month, last)
