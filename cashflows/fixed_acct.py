"""
§13 — Fixed Account AV Waterfall  (Step 18)

Fixed-account AV projection for six stacks: POR, MGA, POR-MultiFund,
POR-Portland, 401K, DCA Account.

Test policy 842612365: fixed_account_value = $0 → all stacks zero throughout.
Full crediting-rate mechanics (GA Curr, GA Guar, DCA transfers) are deferred
to the cashflow engine integration once fixed_account_value > 0 is encountered.

Output columns (time-axis pass-through + 3 aggregate):
    av_bop_fa, av_eop_fa, credited_rate_fa
All zero for the test policy.
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


def build_fixed_acct(
    time_axis: pd.DataFrame,
    policy: dict[str, Any],
    assumptions: dict[str, pd.DataFrame],
    config: Any,
) -> pd.DataFrame:
    """
    Project fixed-account AV through all projection periods.

    For the test policy (fixed_account_value = 0), returns a zero DataFrame.
    Full multi-stack mechanics will be activated once a non-zero fixed account
    is encountered.

    Returns
    -------
    DataFrame (index=projection_period) with columns:
        [time-axis pass-through], av_bop_fa, av_eop_fa, credited_rate_fa
    """
    if time_axis.empty:
        warn("time_axis is empty — returning empty fixed_acct DataFrame.",
             source="fixed_acct/empty_time_axis")
        return pd.DataFrame()

    initial_av = float(policy.get("fixed_account_value") or 0.0)

    time_cols = [c for c in _TIME_COLS if c in time_axis.columns]
    df = time_axis[time_cols].copy()

    if initial_av == 0.0:
        df["av_bop_fa"]       = 0.0
        df["av_eop_fa"]       = 0.0
        df["credited_rate_fa"] = 0.0
        df.index.name = "projection_period"
        return df

    # ---- Non-zero fixed account: stub with warn (full mechanics deferred) ----
    warn(
        f"fixed_account_value = {initial_av:.2f} — full fixed-account crediting "
        "mechanics not yet implemented.  av_bop_fa / av_eop_fa will be zero.",
        source="fixed_acct/non_zero_stub",
    )
    df["av_bop_fa"]       = 0.0
    df["av_eop_fa"]       = 0.0
    df["credited_rate_fa"] = 0.0
    df.index.name = "projection_period"
    return df
