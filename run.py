"""
Abc_corp VA Python Valuation Model â€” Single-Policy Runner
=========================================================

Run from the abc_corp_va/ directory in VS Code terminal:

    python run.py

Or with explicit arguments:

    python run.py --reserve-basis NYREG213 --reserve-method CARVM
    python run.py --months 480 --output-dir results/vm21pa/

Arguments (all optional â€” defaults work for the test policy):
  --policy-path      PATH    Input_PolicyDataRaw.xlsx   [data/Input_PolicyDataRaw.xlsx]
  --assumptions-path PATH    Assumptions_Extracted.xlsx [data/Assumptions_Extracted.xlsx]
  --output-dir       DIR     Output directory           [results/]
  --output-file      NAME    Excel filename             [abc_corp_va_output.xlsx]
  --reserve-basis    BASIS   VM21PA|VM21CA|NYREG213|GAAPDAC|CAPITAL  [VM21PA]
  --reserve-method   METHOD  StdScn|CARVM|OptionValueFloor            [StdScn]
  --months           N       Projection months          [480]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Abc_corp VA single-policy valuation model",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--policy-path", default="data/Input_PolicyDataRaw.xlsx",
        help="Path to Input_PolicyDataRaw.xlsx",
    )
    p.add_argument(
        "--assumptions-path", default="data/Assumptions_Extracted.xlsx",
        help="Path to Assumptions_Extracted.xlsx",
    )
    p.add_argument("--output-dir",  default="results/",   help="Output directory")
    p.add_argument("--output-file", default=None,
                   help="Output Excel filename (default: abc_corp_va_<policy_id>.xlsx)")
    p.add_argument(
        "--reserve-basis", default="VM21PA",
        choices=["VM21PA", "VM21CA", "NYREG213", "GAAPDAC", "CAPITAL"],
    )
    p.add_argument(
        "--reserve-method", default="StdScn",
        choices=["StdScn", "CARVM", "OptionValueFloor"],
    )
    p.add_argument("--months", default=480, type=int, help="Projection months")
    p.add_argument(
        "--policy-id", default=None,
        help="Policy number to run (e.g. 842612365 or 999999999). "
             "Defaults to the first row in the policy file.",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def main() -> Path:
    args = _parse_args()

    policy_path      = str(Path(args.policy_path).resolve())
    assumptions_path = str(Path(args.assumptions_path).resolve())
    output_dir       = str(Path(args.output_dir).resolve())

    # Input validation
    for label, path in [("--policy-path", policy_path),
                         ("--assumptions-path", assumptions_path)]:
        if not Path(path).exists():
            sys.exit(f"ERROR: file not found ({label}): {path}")

    t0 = time.time()
    _banner(args, policy_path, assumptions_path)

    # ---- [1] Config ---------------------------------------------------------
    _step(1, 15, "Config")
    from config import Config
    cfg = Config(
        policy_path=policy_path,
        assumptions_path=assumptions_path,
        output_dir=output_dir,
        reserve_basis=args.reserve_basis,
        reserve_method=args.reserve_method,
        projection_months=args.months,
    )

    # ---- [2] Policy ---------------------------------------------------------
    _step(2, 15, "Policy loader")
    from loaders.policy_loader import load_policy
    policy = load_policy(policy_path, policy_id=args.policy_id)
    _info(f"Policy {policy.get('policy_number')}  "
          f"Plan: {policy.get('plan') or policy.get('model_plan')}  "
          f"AV: ${float(policy.get('total_account_value', 0)):>14,.2f}")

    # ---- [3] Assumptions ----------------------------------------------------
    _step(3, 15, "Assumption loader")
    from loaders.assumption_loader import load_assumptions
    assumptions = load_assumptions(assumptions_path)
    _info(f"{len(assumptions)} assumption tables loaded")

    # ---- [4] Scenarios ------------------------------------------------------
    _step(4, 15, "Scenario loader")
    from loaders.scenario_loader import load_scenarios
    scenarios = load_scenarios(policy_path)
    _info(f"Run ID: {scenarios.run_id}  Scenario: {scenarios.scn_name}")

    # ---- [5] Time axis ------------------------------------------------------
    _step(5, 15, "Time axis")
    from decrements.time_axis import build_time_axis
    time_axis = build_time_axis(policy, cfg)
    _info(f"{len(time_axis)} periods  "
          f"BOP[1]={time_axis.loc[1,'bop_date']}  "
          f"EOP[{len(time_axis)}]={time_axis.iloc[-1]['eop_date']}")

    # ---- [6] Mortality ------------------------------------------------------
    _step(6, 15, "Mortality engine")
    from decrements.mortality import build_mortality
    mortality = build_mortality(time_axis, policy, assumptions, cfg)

    # ---- [7] Lapse ----------------------------------------------------------
    _step(7, 15, "Lapse engine")
    from decrements.lapse import build_lapse
    lapse = build_lapse(time_axis, policy, assumptions, cfg)
    _info(f"q_lapse_monthly[1] = {float(lapse.loc[1,'q_lapse_monthly']):.6f}  "
          f"(ITM bucket = {float(lapse.loc[1,'itm_bucket']):.2f})")

    # ---- [8] Lives ----------------------------------------------------------
    _step(8, 15, "Lives engine")
    from decrements.lives import build_lives
    lives = build_lives(mortality, lapse, cfg)
    _info(f"lives_bop[1] = {float(lives.loc[1,'lives_bop']):.4f}")

    # ---- [9] Interest rates -------------------------------------------------
    _step(9, 15, "Interest rates")
    from cashflows.interest import build_interest_rates
    interest_rates = build_interest_rates(time_axis, scenarios, cfg)
    _info(f"BEY[1] = {float(interest_rates.loc[1,'i_bey_pct']):.2f}%  "
          f"disc_factor[1] = {float(interest_rates.loc[1,'disc_factor']):.8f}  "
          f"(shocked: {float(interest_rates.loc[1,'disc_factor_shock']):.8f})")

    # ---- [10] Fund mechanics ------------------------------------------------
    _step(10, 15, "Fund mechanics")
    from cashflows.fund_mechanics import build_fund_mechanics
    fund_mechanics = build_fund_mechanics(time_axis, scenarios, cfg)
    _info(f"growth_f1[1] = {float(fund_mechanics.loc[1,'growth_f1']):.6f}  "
          f"(EQ_Growth = {float(scenarios.get('S&P 500-EQ_Growth')[1]):.2f}%)")

    # ---- [11] i4L rider -----------------------------------------------------
    _step(11, 15, "i4L rider")
    from cashflows.i4l import build_i4l
    i4l = build_i4l(time_axis, policy, assumptions, cfg)
    _info(f"AP remaining[1] = {int(i4l.loc[1,'o_ap_remaining'])}  "
          f"V[1] = {float(i4l.loc[1,'v_ap_annuity']):.6f}")

    # ---- [12] Cashflow engine -----------------------------------------------
    _step(12, 15, "Cashflow engine")
    from cashflows.cashflow_engine import build_cashflows
    cashflows_df = build_cashflows(time_axis, policy, fund_mechanics, i4l, cfg)
    _info(f"av_bop_sa[1] = ${float(cashflows_df.loc[1,'av_bop_sa']):>14,.2f}  "
          f"av_eop_sa[1] = ${float(cashflows_df.loc[1,'av_eop_sa']):>14,.2f}")

    # Separate account (standalone for output â€” cashflow engine is authoritative)
    from cashflows.sep_acct import build_sep_acct
    sep_acct = build_sep_acct(time_axis, policy, fund_mechanics, cfg)

    # ---- [13] Reserve -------------------------------------------------------
    _step(13, 15, "Reserve calculation")
    from reserve.decremented_cf import apply_lives
    dec_cf = apply_lives(cashflows_df, lives)

    from reserve.std_scn_anr import calculate_std_scn_anr
    std_scn = calculate_std_scn_anr(dec_cf, interest_rates, policy, cfg)

    from reserve.carvm import calculate_carvm
    carvm = calculate_carvm(dec_cf, interest_rates, policy, cfg)

    from reserve.dac import calculate_dac
    dac = calculate_dac(dec_cf, lives, policy, cfg)

    from reserve.reserve_aggregator import aggregate_reserves
    reserve = aggregate_reserves(std_scn, carvm, dac, policy, cfg)

    reserve_t0 = float(reserve["reserve_t0"].iloc[0])
    _info(f"FINAL RESERVE (t=0): ${reserve_t0:>12,.2f}  "
          f"[{args.reserve_basis} + {args.reserve_method}]")

    # ---- [14] Output --------------------------------------------------------
    _step(14, 15, "Writing output")
    # Auto-generate filename from policy number if not specified
    pol_num = str(policy.get("policy_number", "unknown")).strip()
    out_filename = args.output_file or f"abc_corp_va_{pol_num}.xlsx"

    from output.writer import write_output
    out_path = write_output(
        policy=policy,
        config=cfg,
        time_axis=time_axis,
        mortality=mortality,
        lapse=lapse,
        lives=lives,
        interest_rates=interest_rates,
        fund_mechanics=fund_mechanics,
        sep_acct=sep_acct,
        i4l=i4l,
        cashflows=cashflows_df,
        dec_cf=dec_cf,
        std_scn=std_scn,
        carvm=carvm,
        dac=dac,
        reserve=reserve,
        output_dir=output_dir,
        filename=out_filename,
    )

    # ---- [15] Summary -------------------------------------------------------
    elapsed = time.time() - t0
    from loaders.warnings import get_warnings
    warns = get_warnings()

    print()
    print("=" * 60)
    print(f"  COMPLETE  ({elapsed:.1f}s)")
    print(f"  Output:   {out_path}")
    print(f"  Reserve:  ${reserve_t0:,.2f}  [{args.reserve_basis}+{args.reserve_method}]")
    if warns:
        print(f"  Warnings: {len(warns)}  (see 'Warnings' sheet)")
    print("=" * 60)

    return out_path


# ---------------------------------------------------------------------------
# Console helpers
# ---------------------------------------------------------------------------

def _banner(args, policy_path: str, assumptions_path: str) -> None:
    print()
    print("=" * 60)
    print("  Abc_corp VA Python Valuation Model")
    print("=" * 60)
    print(f"  Policy:       {Path(policy_path).name}")
    print(f"  Assumptions:  {Path(assumptions_path).name}")
    print(f"  Basis/Method: {args.reserve_basis} + {args.reserve_method}")
    print(f"  Months:       {args.months}")
    print("=" * 60)
    print()


def _step(n: int, total: int, label: str) -> None:
    print(f"[{n:>2}/{total}] {label} ...")


def _info(msg: str) -> None:
    print(f"       {msg}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
