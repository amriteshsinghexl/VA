"""
Orchestrator — wires all three layers together for a single policy run.

Call order (enforced — do not reorder):
  1. loaders: load policy, assumptions, scenarios
  2. decrements: time_axis → mortality → lapse → lives
  3. cashflows: fund_mechanics → sep_acct → fixed_acct → i4l → k401
               → benefit_base → charges → withdrawals → premium_suspension
               → cashflow_engine
  4. reserve: decremented_cf → carvm / std_scn_anr / dac → reserve_aggregator
  5. output: output_builder
"""
from __future__ import annotations

from config import Config


def run(config: Config) -> None:
    """Execute the full valuation pipeline for one policy."""
    raise NotImplementedError("DUMMY — orchestrator not yet implemented")
