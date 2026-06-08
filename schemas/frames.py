"""
Pandera DataFrameSchema contracts for the three-layer output DataFrames.

Each schema is used only as a validation checkpoint; no business logic lives here.
Column lists match the workbook output columns exactly — populated in later steps.
"""
import pandera.pandas as pa
from pandera.pandas import Column, DataFrameSchema


# ---------------------------------------------------------------------------
# Layer 1a — Decrements
# Rows: projection months 1–480. Index is 1-based integer month.
# Populated by: decrements/lives.py (which consumes mortality.py + lapse.py)
# ---------------------------------------------------------------------------
DecrementsFrame = DataFrameSchema(
    {
        "month": Column(int, nullable=False),
        "lives_bop": Column(float, nullable=False),
        "lives_eop": Column(float, nullable=False),
        "q_mort_monthly": Column(float, nullable=False),
        "q_lapse_monthly": Column(float, nullable=False),
    },
    index=pa.Index(int),
    strict=False,   # allow additional columns; exact set defined in step 10
    coerce=True,
)

# ---------------------------------------------------------------------------
# Layer 1b — Undecremented Cashflows
# Rows: projection months 1–480. All cash-flow amounts are per-unit (1 life).
# Populated by: cashflows/cashflow_engine.py
# ---------------------------------------------------------------------------
UndecCashflowFrame = DataFrameSchema(
    {
        "month": Column(int, nullable=False),
        "sep_acct_av": Column(float, nullable=True),
        "fixed_acct_av": Column(float, nullable=True),
        "total_av": Column(float, nullable=True),
    },
    index=pa.Index(int),
    strict=False,
    coerce=True,
)

# ---------------------------------------------------------------------------
# Layer 2 — Decremented Cashflows
# Rows: projection months 1–480. Amounts are undec × lives_eop.
# Populated by: reserve/decremented_cf.py
# ---------------------------------------------------------------------------
DecCashflowFrame = DataFrameSchema(
    {
        "month": Column(int, nullable=False),
        "dec_sep_acct_av": Column(float, nullable=True),
        "dec_fixed_acct_av": Column(float, nullable=True),
        "dec_total_av": Column(float, nullable=True),
    },
    index=pa.Index(int),
    strict=False,
    coerce=True,
)
