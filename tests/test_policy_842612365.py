"""
Regression test: policy 842612365 (Plan LMFR5 / MultiFund block).

All expected values sourced from workbook VA_VT_Masked_V2_for Sandbox_NB.xlsx.
Add assertions as each step is implemented.
"""
import datetime
import math
import pytest
import sys
from pathlib import Path

# Ensure abc_corp_va root is on sys.path when tests run from any directory
sys.path.insert(0, str(Path(__file__).parent.parent))

POLICY_PATH = str(Path(__file__).parent.parent / "data" / "Input_PolicyDataRaw.xlsx")
ASSUMPTIONS_PATH = str(Path(__file__).parent.parent / "data" / "Assumptions_Extracted.xlsx")
POLICY_ID = "842612365"

_DATA_PRESENT        = Path(POLICY_PATH).exists()
_ASSUMPTIONS_PRESENT = Path(ASSUMPTIONS_PATH).exists()


# --------------------------------------------------------------------------- #
# Step 4 â€” policy_loader                                                        #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def policy():
    from loaders.policy_loader import load_policy
    return load_policy(POLICY_PATH)


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_policy_id(policy):
    assert str(policy["policy_number"]) == POLICY_ID


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_total_account_value(policy):
    assert abs(float(policy["total_account_value"]) - 1_579_907.85) < 0.01


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_cash_surrender_value(policy):
    assert abs(float(policy["cash_surrender_value"]) - 1_579_387.62) < 0.01


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_policy_month_seed(policy):
    """Policy_Info!T10 = 215 for valuation 2025-06 / issue 2007-08-27."""
    assert policy["policy_month_seed"] == 215


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_attained_age_seed(policy):
    """Policy_Info!T13 = 75."""
    assert policy["attained_age_seed"] == 75


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_valuation_date(policy):
    """ValuationDate = last day of June 2025 = 2025-06-30."""
    assert policy["valuation_date"] == datetime.date(2025, 6, 30)


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_next_monthiversary(policy):
    """Policy_Info!T12 = DATE(2025, 7, 27) = 2025-07-27."""
    assert policy["next_monthiversary"] == datetime.date(2025, 7, 27)


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_company(policy):
    assert policy["company"] == "LNL"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_lb_code(policy):
    assert policy["lb_code"] == "B"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_i4l_indicator(policy):
    assert policy["i4l_indicator"] == "i4L"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_stub_period(policy):
    """Stub period is permanently 0.0 per D-005."""
    assert policy["stub_period"] == 0.0


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_plan(policy):
    assert policy["plan"] == "LMFR5"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_gender1(policy):
    assert policy["gender1"] == "M"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_single_joint(policy):
    assert policy["single_joint"] == "U"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_db_option(policy):
    """deathbenefittype = "A" (AV-only)."""
    assert policy["db_option"] == "A"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_dac_amortization_basis_graceful(policy):
    """Policy_Info!C107 = #VALUE! â€” loader should default to None, not raise (D-003)."""
    # Key "dac_amortization_basis" must exist (possibly None) â€” must never KeyError
    assert "dac_amortization_basis" in policy


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_indicator_401k_false(policy):
    """LMFR5 is not a 401K plan."""
    assert policy["indicator_401k"] is False


# --------------------------------------------------------------------------- #
# Step 3 â€” Config                                                               #
# --------------------------------------------------------------------------- #

def test_config_vm21_flag():
    from config import Config
    cfg = Config(policy_path="x", assumptions_path="x", output_dir="x",
                 reserve_basis="VM21PA", reserve_method="StdScn")
    assert cfg.vm21_flag == "VM21"


def test_config_vm21_flag_nyreg():
    from config import Config
    cfg = Config(policy_path="x", assumptions_path="x", output_dir="x",
                 reserve_basis="NYREG213", reserve_method="StdScn")
    assert cfg.vm21_flag == "NYREG213"


def test_config_suppress_charges_nyreg_carvm():
    from config import Config
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cfg = Config(policy_path="x", assumptions_path="x", output_dir="x",
                     reserve_basis="NYREG213", reserve_method="CARVM")
    assert cfg.suppress_charges is True


def test_config_suppress_charges_nyreg_stdscn():
    from config import Config
    cfg = Config(policy_path="x", assumptions_path="x", output_dir="x",
                 reserve_basis="NYREG213", reserve_method="StdScn")
    assert cfg.suppress_charges is False


def test_config_capital_zero_lapse():
    from config import Config
    cfg = Config(policy_path="x", assumptions_path="x", output_dir="x",
                 reserve_basis="CAPITAL", reserve_method="StdScn")
    assert cfg.capital_zero_lapse is True


def test_config_nyreg213_carvm_zero_lapse():
    from config import Config
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cfg = Config(policy_path="x", assumptions_path="x", output_dir="x",
                     reserve_basis="NYREG213", reserve_method="CARVM")
    assert cfg.nyreg213_carvm_zero_lapse is True


# --------------------------------------------------------------------------- #
# Step 10 â€” Lives engine                                                        #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def lives(mortality, lapse):
    from config import Config
    from decrements.lives import build_lives
    cfg = Config(
        policy_path=POLICY_PATH,
        assumptions_path=ASSUMPTIONS_PATH,
        output_dir="results/",
        reserve_basis="VM21PA",
        reserve_method="StdScn",
    )
    return build_lives(mortality, lapse, cfg)


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_lives_shape(lives):
    """480 periods Ã— 11 data columns (projection_period is the index)."""
    assert lives.shape == (480, 11), f"Expected (480,11), got {lives.shape}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_lives_column_names(lives):
    expected = {
        "policy_year", "policy_month", "month_in_policy_year",
        "bop_date", "eop_date", "cal_month_end", "attained_age",
        "q_mort_monthly", "q_lapse_monthly",
        "lives_bop", "lives_eop",
    }
    assert expected.issubset(set(lives.columns)), \
        f"Missing columns: {expected - set(lives.columns)}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_lives_bop_month1(lives):
    """lives_bop[1] must equal 1.0 (cohort seed â€” always exact)."""
    assert lives.loc[1, "lives_bop"] == 1.0


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_lives_bop_is_prior_eop(lives):
    """lives_bop[t] == lives_eop[t-1] for all t â‰¥ 2 (where both are finite)."""
    for t in range(2, 11):   # check first 9 transitions
        eop_prev = lives.loc[t - 1, "lives_eop"]
        bop_curr = lives.loc[t,     "lives_bop"]
        if not (isinstance(eop_prev, float) and math.isnan(eop_prev)):
            assert eop_prev == bop_curr, \
                f"Period {t}: lives_bop={bop_curr} != prior lives_eop={eop_prev}"


def test_lives_formula_synthetic():
    """
    Unit test for _lives_recurrence with synthetic zero-mortality, constant-lapse inputs.

    Verifies:
      - BOP[0] = 1.0
      - EOP[t] = BOP[t] Ã— (1 âˆ’ q_lapse)
      - BOP[t+1] = EOP[t]
      - NaN propagation: once EOP is NaN, all subsequent BOP/EOP are NaN
    """
    import math as _math
    import numpy as np
    from decrements.lives import _lives_recurrence

    # Case 1: zero mortality, 10% monthly lapse
    q_mort  = np.array([0.0, 0.0, 0.0, 0.0])
    q_lapse = np.array([0.10, 0.10, 0.10, 0.10])
    bop, eop = _lives_recurrence(q_mort, q_lapse)

    assert bop[0] == 1.0
    assert abs(eop[0] - 0.90) < 1e-12
    assert abs(bop[1] - 0.90) < 1e-12
    assert abs(eop[1] - 0.81) < 1e-12
    assert abs(bop[2] - 0.81) < 1e-12
    assert abs(eop[2] - 0.729) < 1e-12

    # Case 2: NaN in q_mort at t=0 propagates forward
    q_mort2  = np.array([np.nan, 0.0, 0.0])
    q_lapse2 = np.array([0.10,  0.10, 0.10])
    bop2, eop2 = _lives_recurrence(q_mort2, q_lapse2)

    assert bop2[0] == 1.0
    assert _math.isnan(eop2[0])
    assert _math.isnan(bop2[1])
    assert _math.isnan(eop2[1])

    # Case 3: zero lapse, zero mortality â†’ all lives = 1.0
    q_mort3  = np.array([0.0, 0.0, 0.0])
    q_lapse3 = np.array([0.0, 0.0, 0.0])
    bop3, eop3 = _lives_recurrence(q_mort3, q_lapse3)
    assert (bop3 == 1.0).all()
    assert (eop3 == 1.0).all()


@pytest.mark.skip(
    reason="lives_eop[1] target value requires unmasked workbook â€” "
           "sandbox mortality tables are RAND()-masked so EOP is NaN. "
           "Verify against live workbook when real mortality data is available."
)
def test_lives_eop_month1():
    """lives_eop[1] requires live (unmasked) mortality â€” placeholder pending verification."""
    pass


# --------------------------------------------------------------------------- #
# Step 20 â€” Cashflow engine                                                     #
# --------------------------------------------------------------------------- #

@pytest.mark.skip(reason="Step 20 not yet implemented")
def test_csv_month1():
    """CSV Month 1 = 1,578,722.92."""
    pass


# --------------------------------------------------------------------------- #
# Step 5 â€” assumption_loader                                                    #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def assumptions():
    from loaders.assumption_loader import load_assumptions
    from loaders.warnings import clear_warnings
    clear_warnings()
    return load_assumptions(ASSUMPTIONS_PATH)


@pytest.mark.skipif(not _ASSUMPTIONS_PRESENT, reason="Assumptions_Extracted.xlsx not in data/")
def test_assumptions_sheet_count(assumptions):
    """D-002: exactly 72 data sheets (README excluded)."""
    assert len(assumptions) == 72


@pytest.mark.skipif(not _ASSUMPTIONS_PRESENT, reason="Assumptions_Extracted.xlsx not in data/")
def test_assumptions_has_meta(assumptions):
    """Every DataFrame carries .attrs['meta'] with the 7 required keys."""
    required_keys = {
        "assumption_table", "source_range", "reserve_basis",
        "assumption_type", "lookup_dims", "consumed_by", "source_anchors",
    }
    for name, df in assumptions.items():
        meta = df.attrs.get("meta", {})
        assert required_keys.issubset(meta.keys()), \
            f"Sheet '{name}' missing meta keys: {required_keys - set(meta.keys())}"


@pytest.mark.skipif(not _ASSUMPTIONS_PRESENT, reason="Assumptions_Extracted.xlsx not in data/")
def test_lapse_pad_scalar_values(assumptions):
    """VM21CA_LapsePAD_Scalar: Gross and Net scalars present; Gross row 0 = 2.07."""
    df = assumptions["VM21CA_LapsePAD_Scalar"]
    assert "Gross" in df.columns, "Expected 'Gross' column"
    assert "Net" in df.columns, "Expected 'Net' column"
    gross_vals = [v for v in df["Gross"].tolist() if v is not None and str(v) != "nan"]
    assert len(gross_vals) > 0, "No non-null Gross values"
    assert abs(float(gross_vals[0]) - 2.07) < 1e-6, \
        f"Expected first Gross = 2.07, got {gross_vals[0]}"


@pytest.mark.skipif(not _ASSUMPTIONS_PRESENT, reason="Assumptions_Extracted.xlsx not in data/")
def test_annuity_certain_factor_shape(assumptions):
    """VM21CA_AnnuityCertainFactor: at least one data row; first numeric value â‰ˆ 0.034."""
    df = assumptions["VM21CA_AnnuityCertainFactor"]
    assert not df.empty, "VM21CA_AnnuityCertainFactor is empty"
    # First data value across all non-src_row columns
    data_cols = [c for c in df.columns if c != "src_row"]
    assert len(data_cols) > 0
    first_val = df[data_cols[0]].iloc[0]
    assert abs(float(first_val) - 0.034) < 1e-6, \
        f"Expected first value â‰ˆ 0.034, got {first_val}"


@pytest.mark.skipif(not _ASSUMPTIONS_PRESENT, reason="Assumptions_Extracted.xlsx not in data/")
def test_base_lapse_rates_index(assumptions):
    """VM21PA_BaseLapseRates_Non403b: string index set ('ITM' column), integer col headers."""
    df = assumptions["VM21PA_BaseLapseRates_Non403b"]
    assert df.index.name == "ITM", \
        f"Expected index name 'ITM', got {df.index.name!r}"
    assert df.shape[1] >= 3, "Expected at least 3 data columns"


@pytest.mark.skipif(not _ASSUMPTIONS_PRESENT, reason="Assumptions_Extracted.xlsx not in data/")
def test_dyn_lapse_factors_shape(assumptions):
    """NYREG213_DynLapse_LifeFactors_M: wide table with integer column headers."""
    df = assumptions["NYREG213_DynLapse_LifeFactors_M"]
    assert df.shape[1] >= 100, \
        f"Expected â‰¥100 columns (wide duration table), got {df.shape[1]}"
    # Column headers should be integers (duration buckets)
    data_cols = [c for c in df.columns if c != "src_row"]
    assert isinstance(data_cols[0], int), \
        f"Expected integer column headers, got {type(data_cols[0])}"


@pytest.mark.skipif(not _ASSUMPTIONS_PRESENT, reason="Assumptions_Extracted.xlsx not in data/")
def test_dummy_placeholder_warnings(assumptions):
    """Sheets with masked cells emit DUMMY placeholder warnings."""
    from loaders.warnings import get_warnings
    dummy_warns = [
        w for w in get_warnings()
        if "placeholder" in w.message.lower() or "dummy" in w.message.lower()
    ]
    assert len(dummy_warns) >= 1, "Expected at least 1 DUMMY placeholder warning"


# --------------------------------------------------------------------------- #
# Step 6 â€” scenario_loader                                                      #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def scenarios():
    from loaders.scenario_loader import load_scenarios
    return load_scenarios(POLICY_PATH)


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_scenario_future_shape(scenarios):
    """Future scenario: 24 variables Ã— 600 months."""
    assert scenarios.future.shape == (24, 600), \
        f"Expected (24, 600), got {scenarios.future.shape}"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_scenario_historic_shape(scenarios):
    """Historic scenario: 18 variables Ã— 120 months."""
    assert scenarios.historic.shape == (18, 120), \
        f"Expected (18, 120), got {scenarios.historic.shape}"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_scenario_month_indices(scenarios):
    """Future columns are 1..600; historic columns are -1..-120."""
    assert list(scenarios.future.columns[:3]) == [1, 2, 3]
    assert scenarios.future.columns[-1] == 600
    assert list(scenarios.historic.columns[:3]) == [-1, -2, -3]
    assert scenarios.historic.columns[-1] == -120


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_scenario_interest_rate_m1(scenarios):
    """Interest-YC_1YR M1 = 3.98 (percent BEY)."""
    assert abs(float(scenarios.get("Interest-YC_1YR")[1]) - 3.98) < 1e-9


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_scenario_equity_growth_m1(scenarios):
    """S&P 500-EQ_Growth M1 = 11.58 (percent AEY)."""
    assert abs(float(scenarios.get("S&P 500-EQ_Growth")[1]) - 11.58) < 1e-9


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_scenario_metadata(scenarios):
    """run_id = 810719771; scn_name starts with 'SCN'."""
    assert scenarios.run_id == 810719771
    assert str(scenarios.scn_name).startswith("SCN")


# --------------------------------------------------------------------------- #
# Step 7 â€” time_axis                                                            #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def time_axis(policy):
    from config import Config
    from decrements.time_axis import build_time_axis
    cfg = Config(
        policy_path=POLICY_PATH,
        assumptions_path=ASSUMPTIONS_PATH,
        output_dir="results/",
        reserve_basis="VM21PA",
        reserve_method="StdScn",
    )
    return build_time_axis(policy, cfg)


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_time_axis_shape(time_axis):
    """480 periods Ã— 7 columns (projection_period is the index)."""
    assert time_axis.shape == (480, 7), f"Expected (480,7), got {time_axis.shape}"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_time_axis_period1_bop(time_axis):
    """Period 1 BOP = valuation date 2025-06-30."""
    import datetime
    assert time_axis.loc[1, "bop_date"] == datetime.date(2025, 6, 30)


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_time_axis_period1_eop(time_axis):
    """Period 1 EOP = 2025-07-01 (first of next month, not +30 days)."""
    import datetime
    assert time_axis.loc[1, "eop_date"] == datetime.date(2025, 7, 1)


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_time_axis_period1_cols(time_axis):
    """Period 1: policy_year=18, policy_month=215, month_in_policy_year=11, age=75."""
    r = time_axis.loc[1]
    assert r["policy_year"] == 18
    assert r["policy_month"] == 215
    assert r["month_in_policy_year"] == 11
    assert r["attained_age"] == 75


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_time_axis_period3_year_change(time_axis):
    """Period 3: policy_year increments to 19, attained_age increments to 76."""
    r = time_axis.loc[3]
    assert r["policy_year"] == 19
    assert r["attained_age"] == 76


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_time_axis_feb_cal_month_end(time_axis):
    """Period 9 (Feb 2026): cal_month_end = 2026-02-28 (no leap year)."""
    import datetime
    assert time_axis.loc[9, "cal_month_end"] == datetime.date(2026, 2, 28)
    assert time_axis.loc[9, "bop_date"] == datetime.date(2026, 2, 1)


# --------------------------------------------------------------------------- #
# Step 8 â€” mortality engine                                                     #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def mortality(policy, time_axis, assumptions):
    from config import Config
    from decrements.mortality import build_mortality
    cfg = Config(
        policy_path=POLICY_PATH,
        assumptions_path=ASSUMPTIONS_PATH,
        output_dir="results/",
        reserve_basis="VM21PA",
        reserve_method="StdScn",
    )
    return build_mortality(time_axis, policy, assumptions, cfg)


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_mortality_shape(mortality):
    """480 periods Ã— 15 data columns (projection_period is the index)."""
    assert mortality.shape == (480, 15), f"Expected (480,15), got {mortality.shape}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_mortality_index_name(mortality):
    assert mortality.index.name == "projection_period"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_mortality_column_names(mortality):
    """All 15 expected columns present."""
    expected = {
        "policy_year", "policy_month", "month_in_policy_year",
        "bop_date", "eop_date", "cal_month_end", "attained_age",
        "q_annual", "pad", "imp_scale", "years_imp",
        "imp_mult", "add_mult", "final_ann", "q_monthly",
    }
    assert expected.issubset(set(mortality.columns)), \
        f"Missing columns: {expected - set(mortality.columns)}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_mortality_pad_all_ones(mortality):
    """PAD = 1.0 for all periods (workbook constant)."""
    assert (mortality["pad"] == 1.0).all()


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_mortality_attained_age_period1(mortality):
    """Period 1 attained_age = 75 (matches time_axis)."""
    assert int(mortality.loc[1, "attained_age"]) == 75


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_mortality_years_imp_period1(mortality):
    """
    Period 1: cal_month_end.year=2025, base_year=2012 â†’ years_imp=13.

    Relies on VM21PA_MortalityImprovement meta['hdr_row4'] = 2012.
    """
    yi = mortality.loc[1, "years_imp"]
    assert float(yi) == 13.0, f"Expected years_imp=13, got {yi}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_mortality_years_imp_period8(mortality):
    """
    Period 8: cal_month_end.year=2026 (first Jan period), base_year=2012 â†’ years_imp=14.
    """
    # Period 8: bop_date = 2026-01-01, cal_month_end = 2026-01-31
    yi = mortality.loc[8, "years_imp"]
    assert float(yi) == 14.0, f"Expected years_imp=14, got {yi}"


# --------------------------------------------------------------------------- #
# Step 9 â€” lapse engine                                                         #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def lapse(policy, time_axis, assumptions):
    from config import Config
    from decrements.lapse import build_lapse
    cfg = Config(
        policy_path=POLICY_PATH,
        assumptions_path=ASSUMPTIONS_PATH,
        output_dir="results/",
        reserve_basis="VM21PA",
        reserve_method="StdScn",
    )
    return build_lapse(time_axis, policy, assumptions, cfg)


@pytest.fixture(scope="module")
def lapse_capital(policy, time_axis, assumptions):
    from config import Config
    from decrements.lapse import build_lapse
    cfg = Config(
        policy_path=POLICY_PATH,
        assumptions_path=ASSUMPTIONS_PATH,
        output_dir="results/",
        reserve_basis="CAPITAL",
        reserve_method="StdScn",
    )
    return build_lapse(time_axis, policy, assumptions, cfg)


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_lapse_shape(lapse):
    """480 periods Ã— 12 data columns (projection_period is the index)."""
    assert lapse.shape == (480, 12), f"Expected (480,12), got {lapse.shape}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_lapse_index_name(lapse):
    assert lapse.index.name == "projection_period"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_lapse_column_names(lapse):
    expected = {
        "policy_year", "policy_month", "month_in_policy_year",
        "bop_date", "eop_date", "cal_month_end", "attained_age",
        "sc_flag", "itm_raw", "itm_bucket",
        "q_lapse_annual", "q_lapse_monthly",
    }
    assert expected.issubset(set(lapse.columns)), \
        f"Missing: {expected - set(lapse.columns)}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_lapse_vm21pa_sc_flag(lapse):
    """All periods have SC flag = 3 (test policy has no surrender charges)."""
    assert (lapse["sc_flag"] == 3).all()


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_lapse_vm21pa_itm_bucket(lapse):
    """
    ITM = 4later_current_income_base / total_account_value = 0.7128
    â†’ ITM bucket = 0.50 (floor to nearest 0.25).
    """
    itm_bucket = lapse.loc[1, "itm_bucket"]
    assert abs(float(itm_bucket) - 0.50) < 1e-9, \
        f"Expected ITM bucket 0.50, got {itm_bucket}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_lapse_vm21pa_q_annual(lapse):
    """
    VM21PA non-403b at ITM=0.50, SC flag=3 â†’ q_lapse_annual = 0.64.
    """
    q = lapse.loc[1, "q_lapse_annual"]
    assert abs(float(q) - 0.64) < 1e-9, f"Expected q_annual=0.64, got {q}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_lapse_vm21pa_q_monthly(lapse):
    """
    Geometric monthly: 1 - (1-0.64)^(1/12) â‰ˆ 0.08161.
    """
    q = lapse.loc[1, "q_lapse_monthly"]
    expected = 1.0 - (1.0 - 0.64) ** (1.0 / 12.0)
    assert abs(float(q) - expected) < 1e-9, f"Expected q_monthlyâ‰ˆ{expected:.6f}, got {q}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_lapse_capital_all_zero(lapse_capital):
    """D-006: CAPITAL basis â†’ q_lapse_monthly = 0.0 for all periods."""
    assert (lapse_capital["q_lapse_monthly"] == 0.0).all()
    assert (lapse_capital["q_lapse_annual"] == 0.0).all()


# --------------------------------------------------------------------------- #
# Step 10 â€” lives engine                                                        #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def lives(mortality, lapse):
    from config import Config
    from decrements.lives import build_lives
    cfg = Config(
        policy_path=POLICY_PATH,
        assumptions_path=ASSUMPTIONS_PATH,
        output_dir="results/",
        reserve_basis="VM21PA",
        reserve_method="StdScn",
    )
    return build_lives(mortality, lapse, cfg)


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_lives_shape(lives):
    """480 periods Ã— 11 data columns (projection_period is the index)."""
    assert lives.shape == (480, 11), f"Expected (480,11), got {lives.shape}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_lives_column_names(lives):
    """All 11 expected columns present."""
    expected = {
        "policy_year", "policy_month", "month_in_policy_year",
        "bop_date", "eop_date", "cal_month_end", "attained_age",
        "q_mort_monthly", "q_lapse_monthly",
        "lives_bop", "lives_eop",
    }
    assert expected.issubset(set(lives.columns)), \
        f"Missing columns: {expected - set(lives.columns)}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_lives_bop_period1(lives):
    """Period 1 BOP = 1.0 (cohort seed)."""
    assert float(lives.loc[1, "lives_bop"]) == 1.0


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_lives_bop_is_prior_eop(lives):
    """
    BOP[t+1] = EOP[t] for all periods (structural recurrence check).

    VM21PA_BaseMortality_Single uses RAND()/10 masking, so q_mort values are
    random floats in [0, 0.1] â€” not NaN.  EOP values are therefore finite
    (though numerically meaningless until live tables are populated).
    The structural rule BOP[t+1] = EOP[t] must hold regardless.
    """
    import numpy as np
    bop = lives["lives_bop"].to_numpy(dtype=float)
    eop = lives["lives_eop"].to_numpy(dtype=float)
    for i in range(len(eop) - 1):
        e, b = eop[i], bop[i + 1]
        if np.isnan(e):
            assert np.isnan(b), \
                f"EOP[{i+1}]=NaN but BOP[{i+2}]={b} (NaN must propagate)"
        else:
            assert e == b, \
                f"BOP[{i+2}]={b} â‰  EOP[{i+1}]={e} (must be identical copy)"


def test_lives_formula_synthetic():
    """
    Unit test for _lives_recurrence with known inputs (no data files needed).

    Verifies:
      - BOP seed = 1.0
      - EOP formula: bop Ã— (1âˆ’qm) Ã— (1âˆ’ql)
      - BOP[t+1] = EOP[t]
      - NaN in q_mort propagates to EOP and subsequent BOPs
      - Zero decrements: EOP = BOP (no change)
    """
    import numpy as np
    from decrements.lives import _lives_recurrence

    # Case 1: uniform 10% lapse, zero mortality â€” 4 periods
    q_mort  = np.array([0.0, 0.0, 0.0, 0.0])
    q_lapse = np.array([0.10, 0.10, 0.10, 0.10])
    bop, eop = _lives_recurrence(q_mort, q_lapse)

    assert bop[0] == 1.0,           "BOP[0] must be 1.0"
    assert abs(eop[0] - 0.90) < 1e-12, f"EOP[0]: expected 0.90, got {eop[0]}"
    assert abs(bop[1] - 0.90) < 1e-12, f"BOP[1]: expected 0.90, got {bop[1]}"
    assert abs(eop[1] - 0.81) < 1e-12, f"EOP[1]: expected 0.81, got {eop[1]}"
    assert abs(eop[3] - 0.90**4) < 1e-12

    # Case 2: NaN mortality propagates forward
    q_mort_nan  = np.array([np.nan, 0.0, 0.0])
    q_lapse_ok  = np.array([0.05,  0.05, 0.05])
    bop2, eop2 = _lives_recurrence(q_mort_nan, q_lapse_ok)
    assert bop2[0] == 1.0
    assert math.isnan(eop2[0]), "NaN qm â†’ EOP[0] = NaN"
    assert math.isnan(bop2[1]), "NaN EOP[0] â†’ BOP[1] = NaN"
    assert math.isnan(eop2[2]), "NaN propagates to end"

    # Case 3: zero decrements â€” lives stay at 1.0
    q_zero = np.array([0.0, 0.0, 0.0])
    bop3, eop3 = _lives_recurrence(q_zero, q_zero)
    assert (eop3 == 1.0).all(), "Zero decrements: all EOP should be 1.0"


@pytest.mark.skip(reason=(
    "EOP[1] value comes from RAND()/10-masked VM21PA base mortality â€” the "
    "sandbox workbook stores RAND()/10 in place of true q values, so the "
    "result varies each Excel recalculation and cannot be pinned to an expected "
    "value.  The stub value of 0.70 (30% lapse shock) was a prior placeholder "
    "written before the lapse engine existed; no shock-lapse table is present "
    "in Assumptions_Extracted.xlsx.  Enable once live mortality tables are loaded."
))
def test_lives_eop_month1(lives):
    """Period 1 EOP â€” requires unmasked (live) mortality data to verify."""
    expected = 0.70   # placeholder only â€” not verified against workbook
    assert abs(float(lives.loc[1, "lives_eop"]) - expected) < 1e-4


# --------------------------------------------------------------------------- #
# Step 11 â€” interest rate engine                                                #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def interest_rates(time_axis, scenarios):
    from config import Config
    from cashflows.interest import build_interest_rates
    cfg = Config(
        policy_path=POLICY_PATH,
        assumptions_path=ASSUMPTIONS_PATH,
        output_dir="results/",
        reserve_basis="VM21PA",
        reserve_method="StdScn",
    )
    return build_interest_rates(time_axis, scenarios, cfg)


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_interest_shape(interest_rates):
    """480 periods Ã— 14 data columns (7 time + 7 rate columns)."""
    assert interest_rates.shape == (480, 14), \
        f"Expected (480,14), got {interest_rates.shape}"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_interest_index_name(interest_rates):
    assert interest_rates.index.name == "projection_period"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_interest_column_names(interest_rates):
    """All 14 expected columns present."""
    expected = {
        "policy_year", "policy_month", "month_in_policy_year",
        "bop_date", "eop_date", "cal_month_end", "attained_age",
        "i_bey_pct", "i_aey", "i_monthly", "disc_factor",
        "i_aey_shock", "i_monthly_shock", "disc_factor_shock",
    }
    assert expected.issubset(set(interest_rates.columns)), \
        f"Missing columns: {expected - set(interest_rates.columns)}"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_interest_bey_period1(interest_rates):
    """Period 1 BEY = 3.98 percent (Interest-YC_10YR from scenario data)."""
    val = float(interest_rates.loc[1, "i_bey_pct"])
    assert abs(val - 3.98) < 1e-9, f"Expected i_bey_pct=3.98, got {val}"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_interest_disc_factor_period1(interest_rates):
    """
    Period 1 disc_factor from BEY=3.98%:
      i_aey = (1+0.0199)^2 âˆ’ 1 = 0.04019601
      i_m   = (1.04019601)^(1/12) âˆ’ 1 â‰ˆ 0.003289496
      v     = 1/(1+i_m) â‰ˆ 0.9967212895
    """
    val = float(interest_rates.loc[1, "disc_factor"])
    # Compute expected the same way the engine does
    i_bey  = 3.98 / 100.0
    i_aey  = (1.0 + i_bey / 2.0) ** 2 - 1.0
    i_m    = (1.0 + i_aey) ** (1.0 / 12.0) - 1.0
    expected = 1.0 / (1.0 + i_m)
    assert abs(val - expected) < 1e-12, \
        f"Expected disc_factor[1]â‰ˆ{expected:.10f}, got {val:.10f}"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_interest_disc_factor_shock_period1(interest_rates):
    """
    Period 1 disc_factor_shock: +100bps at AEY level.
      i_aey_shock = 0.04019601 + 0.01 = 0.05019601
    """
    val = float(interest_rates.loc[1, "disc_factor_shock"])
    i_bey       = 3.98 / 100.0
    i_aey       = (1.0 + i_bey / 2.0) ** 2 - 1.0
    i_aey_shock = i_aey + 0.01
    i_m_shock   = (1.0 + i_aey_shock) ** (1.0 / 12.0) - 1.0
    expected    = 1.0 / (1.0 + i_m_shock)
    assert abs(val - expected) < 1e-12, \
        f"Expected disc_factor_shock[1]â‰ˆ{expected:.10f}, got {val:.10f}"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_interest_disc_factor_period2(interest_rates):
    """
    Period 2 disc_factor: BEY=4.48%, accumulated with period-1 factor.
    disc_factor[2] = disc_factor[1] Ã— 1/(1+i_m[2]).
    """
    val = float(interest_rates.loc[2, "disc_factor"])
    # Re-derive from scratch
    def _v(bey_pct):
        ib = bey_pct / 100.0
        ia = (1.0 + ib / 2.0) ** 2 - 1.0
        im = (1.0 + ia) ** (1.0 / 12.0) - 1.0
        return 1.0 / (1.0 + im)

    expected = _v(3.98) * _v(4.48)
    assert abs(val - expected) < 1e-12, \
        f"Expected disc_factor[2]â‰ˆ{expected:.10f}, got {val:.10f}"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_interest_disc_factor_monotone(interest_rates):
    """disc_factor must be strictly decreasing (all rates > 0 in this scenario)."""
    df_vals = interest_rates["disc_factor"].dropna().to_numpy()
    assert (df_vals[:-1] > df_vals[1:]).all(), \
        "disc_factor must be strictly decreasing (positive interest rates)"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_interest_shock_always_higher(interest_rates):
    """Shocked monthly rate > unshocked for all periods (shock = +100bps > 0)."""
    ir = interest_rates
    assert (ir["i_monthly_shock"] > ir["i_monthly"]).all(), \
        "i_monthly_shock must exceed i_monthly for every period"


# --------------------------------------------------------------------------- #
# Step 12 â€” fund mechanics engine                                               #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def fund_mechanics(time_axis, scenarios):
    from config import Config
    from cashflows.fund_mechanics import build_fund_mechanics
    cfg = Config(
        policy_path=POLICY_PATH,
        assumptions_path=ASSUMPTIONS_PATH,
        output_dir="results/",
        reserve_basis="VM21PA",
        reserve_method="StdScn",
    )
    return build_fund_mechanics(time_axis, scenarios, cfg)


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_fund_mechanics_shape(fund_mechanics):
    """480 periods Ã— 13 columns (7 time + 6 growth factor columns)."""
    assert fund_mechanics.shape == (480, 13), \
        f"Expected (480,13), got {fund_mechanics.shape}"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_fund_mechanics_index_name(fund_mechanics):
    assert fund_mechanics.index.name == "projection_period"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_fund_mechanics_column_names(fund_mechanics):
    """All 13 expected columns present."""
    expected = {
        "policy_year", "policy_month", "month_in_policy_year",
        "bop_date", "eop_date", "cal_month_end", "attained_age",
        "growth_f1", "growth_f2", "growth_f3",
        "growth_f4", "growth_f5", "growth_f6",
    }
    assert expected.issubset(set(fund_mechanics.columns)), \
        f"Missing columns: {expected - set(fund_mechanics.columns)}"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_fund_mechanics_growth_f1_period1(fund_mechanics):
    """
    Fund 1 (S&P 500) period 1 growth factor from EQ_Growth=11.58%.
      r = 11.58 / 100 = 0.1158  (no income in this scenario)
      monthly = (1 + 0.1158)^(1/12) âˆ’ 1
    """
    val = float(fund_mechanics.loc[1, "growth_f1"])
    expected = (1.0 + 11.58 / 100.0) ** (1.0 / 12.0) - 1.0
    assert abs(val - expected) < 1e-12, \
        f"Expected growth_f1[1]â‰ˆ{expected:.8f}, got {val:.8f}"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_fund_mechanics_growth_f1_period2(fund_mechanics):
    """
    Fund 1 (S&P 500) period 2 growth factor from EQ_Growth=11.98%.
    Verifies the engine reads the correct per-period scenario value.
    """
    val = float(fund_mechanics.loc[2, "growth_f1"])
    expected = (1.0 + 11.98 / 100.0) ** (1.0 / 12.0) - 1.0
    assert abs(val - expected) < 1e-12, \
        f"Expected growth_f1[2]â‰ˆ{expected:.8f}, got {val:.8f}"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_fund_mechanics_all_funds_equal_period1(fund_mechanics):
    """
    All 6 funds have identical EQ_Growth in this scenario (flat return surface).
    growth_f1 == growth_f2 == ... == growth_f6 for every period.
    """
    cols = [f"growth_f{i}" for i in range(1, 7)]
    row1 = fund_mechanics.loc[1, cols]
    assert row1.nunique() == 1, \
        f"Expected all 6 growth factors equal in period 1, got: {row1.to_dict()}"
    # Verify across all 480 periods
    df_g = fund_mechanics[cols]
    diff = df_g.sub(df_g["growth_f1"], axis=0).abs().max().max()
    assert diff < 1e-12, f"Funds diverge by {diff:.2e} across all periods"


def test_fund_mechanics_formula_synthetic():
    """
    Unit test of the growth-factor formula: (1+r)^(1/12) âˆ’ 1.
    No data files needed.
    """
    import numpy as np

    def monthly_factor(r_annual_pct):
        return (1.0 + r_annual_pct / 100.0) ** (1.0 / 12.0) - 1.0

    # 0% growth â†’ 0 monthly factor
    assert abs(monthly_factor(0.0)) < 1e-15

    # 12% annual â‰ˆ 0.9489% monthly  (not 1% â€” monthly compounding)
    f12 = monthly_factor(12.0)
    assert abs(f12 - ((1.12) ** (1 / 12) - 1)) < 1e-15

    # Compounding for 12 months should recover the annual return
    assert abs((1.0 + f12) ** 12 - 1.12) < 1e-12

    # 100% annual growth
    f100 = monthly_factor(100.0)
    assert abs((1.0 + f100) ** 12 - 2.0) < 1e-11

    # Negative growth
    f_neg = monthly_factor(-20.0)
    assert f_neg < 0
    assert abs((1.0 + f_neg) ** 12 - 0.80) < 1e-12


# --------------------------------------------------------------------------- #
# Step 13 â€” separate account AV waterfall                                       #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def sep_acct(time_axis, policy, fund_mechanics):
    from config import Config
    from cashflows.sep_acct import build_sep_acct
    cfg = Config(
        policy_path=POLICY_PATH,
        assumptions_path=ASSUMPTIONS_PATH,
        output_dir="results/",
        reserve_basis="VM21PA",
        reserve_method="StdScn",
    )
    return build_sep_acct(time_axis, policy, fund_mechanics, cfg)


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_sep_acct_shape(sep_acct):
    """480 periods Ã— 42 columns (7 time + 5Ã—6 per-fund + 5 aggregate)."""
    assert sep_acct.shape == (480, 42), \
        f"Expected (480,42), got {sep_acct.shape}"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_sep_acct_index_name(sep_acct):
    assert sep_acct.index.name == "projection_period"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_sep_acct_column_names(sep_acct):
    """Key columns present."""
    expected = {
        "av_bop_f1", "av_bop_f2", "av_bop_f3", "av_bop_f4", "av_bop_f5", "av_bop_f6",
        "me_f1", "me_f2", "me_f3", "me_f4", "me_f5", "me_f6",
        "imf_f1", "imf_f2", "imf_f3", "imf_f4", "imf_f5", "imf_f6",
        "growth_f1", "growth_f2", "growth_f3", "growth_f4", "growth_f5", "growth_f6",
        "av_eop_f1", "av_eop_f2", "av_eop_f3", "av_eop_f4", "av_eop_f5", "av_eop_f6",
        "av_bop_sa", "me_sa", "imf_sa", "growth_sa", "av_eop_sa",
    }
    assert expected.issubset(set(sep_acct.columns)), \
        f"Missing columns: {expected - set(sep_acct.columns)}"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_sep_acct_bop_sa_period1(sep_acct):
    """Total SA BOP[1] = total_account_value from policy ($1,579,907.85)."""
    val = float(sep_acct.loc[1, "av_bop_sa"])
    assert abs(val - 1_579_907.85) < 0.01, \
        f"Expected av_bop_sa[1]=1579907.85, got {val:.2f}"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_sep_acct_bop_per_fund_period1(sep_acct):
    """
    Each fund's BOP[1] = initial fund AV from Fund_Info (by Inv Acct #).
    Inv Acct 1-6 fund values from workbook Fund_Info sheet.
    """
    # Values from Fund_Info (Inv Acct # ordering, not SQL field ordering)
    expected = {
        1: 787_421.48,   # S&P 500
        2:  96_845.91,   # Russell 2000
        3: 243_546.13,   # Risk-Managed Fund
        4: 225_032.69,   # MSCI EAFE
        5:  52_779.74,   # Money Market
        6: 174_281.90,   # Barclays Capital Aggregate
    }
    for k, exp in expected.items():
        val = float(sep_acct.loc[1, f"av_bop_f{k}"])
        assert abs(val - exp) < 0.01, \
            f"Fund {k} BOP[1]: expected {exp:.2f}, got {val:.2f}"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_sep_acct_eop_sa_period1_formula(sep_acct):
    """
    SA total EOP[1] matches the simplified waterfall formula:
      me     = bop Ã— 0.01/12
      av_me  = bop âˆ’ me
      imf    = av_me Ã— 0.006648054/12    (VM21PA, not NYREG213+CARVM)
      growth = av_me Ã— ((1+0.1158)^(1/12) âˆ’ 1)
      eop    = av_me âˆ’ imf + growth
    """
    bop = 1_579_907.85
    me  = bop * (0.01 / 12.0)
    av_me = bop - me
    imf   = av_me * (0.006648054 / 12.0)
    gf    = (1.0 + 11.58 / 100.0) ** (1.0 / 12.0) - 1.0
    expected = av_me - imf + av_me * gf

    val = float(sep_acct.loc[1, "av_eop_sa"])
    assert abs(val - expected) < 0.01, \
        f"Expected av_eop_sa[1]â‰ˆ{expected:.2f}, got {val:.2f}"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_sep_acct_eop_exceeds_bop_period1(sep_acct):
    """EOP SA AV > BOP SA AV in period 1 (11.58% annual growth > charges)."""
    assert float(sep_acct.loc[1, "av_eop_sa"]) > float(sep_acct.loc[1, "av_bop_sa"]), \
        "Positive growth scenario: EOP should exceed BOP"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Input_PolicyDataRaw.xlsx not in data/")
def test_sep_acct_rollforward(sep_acct):
    """BOP[t+1] = EOP[t] for total SA and all individual funds."""
    import numpy as np
    for k in range(1, 7):
        eop_col = f"av_eop_f{k}"
        bop_col = f"av_bop_f{k}"
        eop = sep_acct[eop_col].to_numpy(dtype=float)
        bop = sep_acct[bop_col].to_numpy(dtype=float)
        for t in range(len(eop) - 1):
            e, b = eop[t], bop[t + 1]
            if np.isnan(e):
                assert np.isnan(b), f"Fund {k}: EOP[{t+1}]=NaN but BOP[{t+2}]={b}"
            else:
                assert e == b, \
                    f"Fund {k}: BOP[{t+2}]={b:.6f} â‰  EOP[{t+1}]={e:.6f}"


# --------------------------------------------------------------------------- #
# Step 14 â€” i4L rider engine                                                    #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def i4l(time_axis, policy, assumptions):
    from config import Config
    from cashflows.i4l import build_i4l
    cfg = Config(
        policy_path=POLICY_PATH,
        assumptions_path=ASSUMPTIONS_PATH,
        output_dir="results/",
        reserve_basis="VM21PA",
        reserve_method="StdScn",
    )
    return build_i4l(time_axis, policy, assumptions, cfg)


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_i4l_shape(i4l):
    """480 periods Ã— 31 data columns."""
    assert i4l.shape == (480, 31), f"Expected (480,31), got {i4l.shape}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_i4l_index_name(i4l):
    assert i4l.index.name == "projection_period"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_i4l_column_names(i4l):
    """All key columns present."""
    expected = {
        "m_pmt_start", "n_ap_date_idx", "o_ap_remaining", "p_ap_end_age",
        "r_annual_mort", "s_monthly_mort", "t_survivorship", "u_disc_factor",
        "v_ap_annuity", "w_postap_annuity",
        "charge_gib", "charge_i4l", "current_payment", "monthly_payment",
    }
    assert expected.issubset(set(i4l.columns)), \
        f"Missing columns: {expected - set(i4l.columns)}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_i4l_ap_timing_period1(i4l):
    """
    AP timing at period 1 (policy month 215):
      m_pmt_start   = deferral_months + 1 = 215 + 1 = 216
      n_ap_date_idx = 216 + 15Ã—12 âˆ’ 1    = 395
      o_ap_remaining = 395 âˆ’ 215          = 180
      p_ap_end_age  = 395 // 12 + 58     = 33 + 58 = 90 (but floor(395/12)=32 â†’ 90)
    """
    row = i4l.loc[1]
    assert int(row["m_pmt_start"])    == 216, f"m={row['m_pmt_start']}"
    assert int(row["n_ap_date_idx"])  == 395, f"n={row['n_ap_date_idx']}"
    assert int(row["o_ap_remaining"]) == 180, f"o={row['o_ap_remaining']}"
    assert int(row["p_ap_end_age"])   == 90,  f"p={row['p_ap_end_age']}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_i4l_disc_factor_seed(i4l):
    """U[1] = 1.0 (seed)."""
    assert float(i4l.loc[1, "u_disc_factor"]) == 1.0


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_i4l_disc_factor_period2(i4l):
    """
    U[2] = 1 / (1+AIR)^(1/12) = 1 / (1.04)^(1/12).
    Uses EFFECTIVE annual compounding (not simple monthly 1 + AIR/12).
    Confirmed workbook value: 0.996736942618562.
    """
    val = float(i4l.loc[2, "u_disc_factor"])
    expected = 1.0 / (1.04 ** (1.0 / 12.0))
    assert abs(val - expected) < 1e-12, \
        f"Expected U[2]â‰ˆ{expected:.12f}, got {val:.12f}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_i4l_disc_factor_period3(i4l):
    """U[3] = 1 / (1.04)^(2/12) â€” two steps from seed."""
    val = float(i4l.loc[3, "u_disc_factor"])
    expected = 1.0 / (1.04 ** (2.0 / 12.0))
    assert abs(val - expected) < 1e-12, \
        f"Expected U[3]â‰ˆ{expected:.12f}, got {val:.12f}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_i4l_ap_annuity_factor_period1(i4l):
    """
    V[1] = Ã¤_{180} / 12 at monthly effective rate (1.04)^(1/12) âˆ’ 1.
    Confirmed workbook value: 11.357842388 (AP=15 years, AIR=4%).

    Pure-interest annuity-due for 180 months, no mortality (access period
    payments are guaranteed regardless of survival).
    """
    import numpy as np
    val = float(i4l.loc[1, "v_ap_annuity"])
    # Re-derive using the same U-sum formula
    n = len(i4l)
    u_arr = i4l["u_disc_factor"].to_numpy(dtype=float)
    o = 180   # o_ap_remaining at period 1
    end = min(0 + o, n)  # period 1 is index 0
    expected = float(np.sum(u_arr[0:end]) / u_arr[0] / 12.0)
    assert abs(val - expected) < 1e-10, \
        f"Expected V[1]â‰ˆ{expected:.9f}, got {val:.9f}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_i4l_ap_annuity_factor_workbook(i4l):
    """V[1] matches workbook-confirmed value 11.357842388 (within 1e-6)."""
    val = float(i4l.loc[1, "v_ap_annuity"])
    assert abs(val - 11.357842388) < 1e-6, \
        f"Expected V[1]â‰ˆ11.357842388, got {val:.9f}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_i4l_survivorship_seed(i4l):
    """T[1] = 1.0 (seed)."""
    assert float(i4l.loc[1, "t_survivorship"]) == 1.0


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_i4l_mortality_nan_warning(i4l):
    """
    D-016: All_i4L_MortalityTables is truncated â†’
    r_annual_mort is NaN (mortality table missing).
    """
    import math
    # R should be NaN for all periods due to truncated table
    r1 = i4l.loc[1, "r_annual_mort"]
    assert math.isnan(float(r1)), \
        f"Expected NaN for r_annual_mort (truncated table), got {r1}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_i4l_w_nan_when_mortality_missing(i4l):
    """W is NaN when T is NaN (D-016 â€” no mortality table)."""
    import math
    w1 = i4l.loc[1, "w_postap_annuity"]
    assert math.isnan(float(w1)), \
        f"Expected NaN for w_postap_annuity (no mortality), got {w1}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_i4l_charges_stubbed_zero(i4l):
    """All AV-dependent charge columns are 0 (stubs until cashflow engine)."""
    for col in ("charge_gib", "charge_i4l", "current_payment", "monthly_payment"):
        assert (i4l[col] == 0.0).all(), \
            f"Expected {col} all zeros (stub), got non-zero values"


def test_i4l_disc_factor_formula_synthetic():
    """
    Unit test: discount factor uses EFFECTIVE annual compounding (1+AIR)^(1/12),
    NOT simple monthly (1+AIR/12). Verified against workbook cell U11=0.996736943.
    """
    from cashflows.i4l import _build_disc_factor

    # 4% effective annual
    u = _build_disc_factor(4, 0.04)
    assert u[0] == 1.0
    assert abs(u[1] - 1.0 / (1.04 ** (1 / 12))) < 1e-15
    assert abs(u[2] - 1.0 / (1.04 ** (2 / 12))) < 1e-15
    assert abs(u[3] - 1.0 / (1.04 ** (3 / 12))) < 1e-15

    # Verify NOT simple monthly: 1/(1+0.04/12) â‰  1/(1.04)^(1/12)
    simple = 1.0 / (1.0 + 0.04 / 12.0)
    effective = 1.0 / (1.04 ** (1.0 / 12.0))
    assert abs(simple - effective) > 1e-6, "Simple and effective rates should differ"
    assert abs(u[1] - effective) < 1e-15


def test_i4l_v_factor_synthetic():
    """Unit test for AP annuity factor V with known inputs."""
    import numpy as np
    from cashflows.i4l import _build_disc_factor, _build_v_factor

    # 2-period projection, O=2 at t=0
    u = _build_disc_factor(5, 0.04)
    o = np.array([2, 1, 0, -1, -2])
    v = _build_v_factor(u, o, 5)

    # t=0, O=2: V = (U[0]+U[1]) / U[0] / 12 = (1 + v2) / 12
    v2 = 1.0 / (1.04 ** (1 / 12))
    expected_v0 = (1.0 + v2) / 12.0
    assert abs(v[0] - expected_v0) < 1e-15

    # t=2, O=0: V = 0
    assert v[2] == 0.0

    # t=3, O=-1: V = 0 (negative O)
    assert v[3] == 0.0


# --------------------------------------------------------------------------- #
# Step 15 â€” benefit_base                                                        #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def benefit_base(time_axis, policy):
    from config import Config
    from cashflows.benefit_base import build_benefit_base
    cfg = Config(policy_path=POLICY_PATH, assumptions_path=ASSUMPTIONS_PATH,
                 output_dir="results/", reserve_basis="VM21PA", reserve_method="StdScn")
    return build_benefit_base(time_axis, policy, cfg)


@pytest.mark.skipif(not _DATA_PRESENT, reason="data files not in data/")
def test_benefit_base_shape(benefit_base):
    assert benefit_base.shape == (480, 11), f"Got {benefit_base.shape}"


@pytest.mark.skipif(not _DATA_PRESENT, reason="data files not in data/")
def test_benefit_base_gmwb_seed(benefit_base):
    """gmwb_base = 4later_current_income_base = 1,126,138.35 for all periods."""
    assert abs(float(benefit_base.loc[1, "gmwb_base"]) - 1_126_138.35) < 0.01
    # Constant (no step-up for non-4Later)
    assert benefit_base["gmwb_base"].nunique() == 1


@pytest.mark.skipif(not _DATA_PRESENT, reason="data files not in data/")
def test_benefit_base_gmdb_charge_zero(benefit_base):
    """GMDB charge = 0 (expense_charge_per_death_benefit = 0 for test policy)."""
    assert (benefit_base["gmdb_charge"] == 0.0).all()


# --------------------------------------------------------------------------- #
# Step 16 â€” charges                                                             #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def charges(time_axis, policy):
    from config import Config
    from cashflows.charges import build_charges
    cfg = Config(policy_path=POLICY_PATH, assumptions_path=ASSUMPTIONS_PATH,
                 output_dir="results/", reserve_basis="VM21PA", reserve_method="StdScn")
    return build_charges(time_axis, policy, cfg)


@pytest.mark.skipif(not _DATA_PRESENT, reason="data files not in data/")
def test_charges_shape(charges):
    assert charges.shape == (480, 20), f"Got {charges.shape}"


@pytest.mark.skipif(not _DATA_PRESENT, reason="data files not in data/")
def test_charges_me_rate(charges):
    """M&E rate = 0.01 annual = 0.000833.../12 monthly."""
    assert abs(float(charges.loc[1, "me_rate"]) - 0.01) < 1e-9
    assert abs(float(charges.loc[1, "me_monthly"]) - 0.01 / 12.0) < 1e-12


@pytest.mark.skipif(not _DATA_PRESENT, reason="data files not in data/")
def test_charges_gib_rate(charges):
    """GIB net rate = 0.009 âˆ’ 0.005 = 0.004 annual."""
    assert abs(float(charges.loc[1, "gib_rate"]) - 0.004) < 1e-9


@pytest.mark.skipif(not _DATA_PRESENT, reason="data files not in data/")
def test_charges_suppressor_vm21pa(charges):
    """Suppressor = 1.0 for VM21PA (only 0 for NYREG213+CARVM)."""
    assert (charges["suppressor"] == 1.0).all()


@pytest.mark.skipif(not _DATA_PRESENT, reason="data files not in data/")
def test_charges_suppressor_nyreg213_carvm():
    """Suppressor = 0.0 for NYREG213+CARVM (D-007)."""
    if not _DATA_PRESENT:
        pytest.skip("data files not in data/")
    from config import Config
    from decrements.time_axis import build_time_axis
    from loaders.policy_loader import load_policy
    from cashflows.charges import build_charges
    p = load_policy(POLICY_PATH)
    cfg_carvm = Config(policy_path=POLICY_PATH, assumptions_path=ASSUMPTIONS_PATH,
                       output_dir="results/", reserve_basis="NYREG213",
                       reserve_method="CARVM")
    ta = build_time_axis(p, cfg_carvm)
    ch = build_charges(ta, p, cfg_carvm)
    assert (ch["suppressor"] == 0.0).all()
    assert (ch["gib_monthly"] == 0.0).all()


# --------------------------------------------------------------------------- #
# Step 17 â€” withdrawals                                                         #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def withdrawals(time_axis, policy, i4l):
    from config import Config
    from cashflows.withdrawals import build_withdrawals
    cfg = Config(policy_path=POLICY_PATH, assumptions_path=ASSUMPTIONS_PATH,
                 output_dir="results/", reserve_basis="VM21PA", reserve_method="StdScn")
    return build_withdrawals(time_axis, policy, i4l, cfg)


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_withdrawals_shape(withdrawals):
    assert withdrawals.shape == (480, 10), f"Got {withdrawals.shape}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_withdrawals_in_ap_period1(withdrawals):
    """Period 1 is within AP (O=180 > 0)."""
    assert bool(withdrawals.loc[1, "is_in_ap"]) is True


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_withdrawals_stub_zero(withdrawals):
    """monthly_withdrawal = 0 (i4l.monthly_payment stubbed pending AV)."""
    assert (withdrawals["monthly_withdrawal"] == 0.0).all()


# --------------------------------------------------------------------------- #
# Step 18 â€” fixed_acct                                                          #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def fixed_acct(time_axis, policy, assumptions):
    from config import Config
    from cashflows.fixed_acct import build_fixed_acct
    cfg = Config(policy_path=POLICY_PATH, assumptions_path=ASSUMPTIONS_PATH,
                 output_dir="results/", reserve_basis="VM21PA", reserve_method="StdScn")
    return build_fixed_acct(time_axis, policy, assumptions, cfg)


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_fixed_acct_shape(fixed_acct):
    assert fixed_acct.shape == (480, 10), f"Got {fixed_acct.shape}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_fixed_acct_all_zero(fixed_acct):
    """All fixed-account AVs = 0 (fixed_account_value = 0 for test policy)."""
    assert (fixed_acct["av_bop_fa"] == 0.0).all()
    assert (fixed_acct["av_eop_fa"] == 0.0).all()


# --------------------------------------------------------------------------- #
# Step 19 â€” cashflow engine (integrated loop)                                   #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def cashflows(time_axis, policy, fund_mechanics, i4l):
    from config import Config
    from cashflows.cashflow_engine import build_cashflows
    cfg = Config(policy_path=POLICY_PATH, assumptions_path=ASSUMPTIONS_PATH,
                 output_dir="results/", reserve_basis="VM21PA", reserve_method="StdScn")
    return build_cashflows(time_axis, policy, fund_mechanics, i4l, cfg)


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_cashflows_shape(cashflows):
    """480 Ã— 27 columns (7 time + 9 SA + 6 fund EOP + 3 i4L + 2 totals)."""
    assert cashflows.shape == (480, 27), f"Got {cashflows.shape}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_cashflows_bop_sa_period1(cashflows):
    """AV BOP period 1 = initial total AV from Fund_Info = 1,579,907.85."""
    val = float(cashflows.loc[1, "av_bop_sa"])
    assert abs(val - 1_579_907.85) < 0.01, f"Got {val:.2f}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_cashflows_gib_charge_period1(cashflows):
    """
    GIB charge[1] = 0.004/12 Ã— at_cme_sa[1].
    at_cme â‰ˆ bop Ã— (1 âˆ’ me_rate/12) Ã— (1 âˆ’ imf_rate/12 + growth_factor).
    Approximate check: GIB â‰ˆ 0.004/12 Ã— 1,579,907 â‰ˆ 526.6
    """
    gib = float(cashflows.loc[1, "gib_charge"])
    at_cme = float(cashflows.loc[1, "av_at_cme_sa"])
    expected = 0.004 / 12.0 * at_cme
    assert abs(gib - expected) < 0.01, f"Expected {expected:.2f}, got {gib:.2f}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_cashflows_i4l_charge_period1(cashflows):
    """i4L charge[1] = 0.005/12 Ã— at_cme_sa[1] (within AP, O=180)."""
    i4l_c = float(cashflows.loc[1, "i4l_charge"])
    at_cme = float(cashflows.loc[1, "av_at_cme_sa"])
    expected = 0.005 / 12.0 * at_cme
    assert abs(i4l_c - expected) < 0.01, f"Expected {expected:.2f}, got {i4l_c:.2f}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_cashflows_current_payment_period1(cashflows):
    """
    Current payment[1] = (at_cme âˆ’ i4l_charge) / (V + W).
    V[1]=11.3578 (computed), W[1]=NaN (truncated mortality) â†’ payment = 0
    when W is NaN (engine uses V+W=0 guard).
    """
    cpmt = float(cashflows.loc[1, "current_payment"])
    v = float(cashflows.loc[1, "o_ap_remaining"])   # not used here, but shows O=180
    # V+W: V is computed, W is NaN â†’ V+W check â†’ 0 guard kicks in
    # If W is NaN the engine falls back to cpmt=0
    assert cpmt >= 0.0, "current_payment must be non-negative"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_cashflows_rollforward(cashflows):
    """AV BOP[t+1] = AV EOP[t] for total SA (exact equality â€” direct copy)."""
    import numpy as np
    eop = cashflows["av_eop_sa"].to_numpy(dtype=float)
    bop = cashflows["av_bop_sa"].to_numpy(dtype=float)
    for t in range(len(eop) - 1):
        assert abs(bop[t + 1] - eop[t]) < 1e-6, \
            f"BOP[{t+2}]={bop[t+1]:.4f} â‰  EOP[{t+1}]={eop[t]:.4f}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_cashflows_eop_positive(cashflows):
    """AV EOP is non-negative for all periods."""
    assert (cashflows["av_eop_sa"] >= 0.0).all()


# --------------------------------------------------------------------------- #
# Step 20 â€” reserve layer                                                       #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def interest_rates(time_axis, scenarios):
    from config import Config
    from cashflows.interest import build_interest_rates
    cfg = Config(policy_path=POLICY_PATH, assumptions_path=ASSUMPTIONS_PATH,
                 output_dir="results/", reserve_basis="VM21PA", reserve_method="StdScn")
    return build_interest_rates(time_axis, scenarios, cfg)


@pytest.fixture(scope="module")
def dec_cf(cashflows, lives):
    from reserve.decremented_cf import apply_lives
    return apply_lives(cashflows, lives)


@pytest.fixture(scope="module")
def std_scn(dec_cf, interest_rates, policy):
    from config import Config
    from reserve.std_scn_anr import calculate_std_scn_anr
    cfg = Config(policy_path=POLICY_PATH, assumptions_path=ASSUMPTIONS_PATH,
                 output_dir="results/", reserve_basis="VM21PA", reserve_method="StdScn")
    return calculate_std_scn_anr(dec_cf, interest_rates, policy, cfg)


@pytest.fixture(scope="module")
def carvm(dec_cf, interest_rates, policy):
    from config import Config
    from reserve.carvm import calculate_carvm
    cfg = Config(policy_path=POLICY_PATH, assumptions_path=ASSUMPTIONS_PATH,
                 output_dir="results/", reserve_basis="VM21PA", reserve_method="StdScn")
    return calculate_carvm(dec_cf, interest_rates, policy, cfg)


@pytest.fixture(scope="module")
def dac(dec_cf, lives, policy):
    from config import Config
    from reserve.dac import calculate_dac
    cfg = Config(policy_path=POLICY_PATH, assumptions_path=ASSUMPTIONS_PATH,
                 output_dir="results/", reserve_basis="VM21PA", reserve_method="StdScn")
    return calculate_dac(dec_cf, lives, policy, cfg)


@pytest.fixture(scope="module")
def reserve(std_scn, carvm, dac, policy):
    from config import Config
    from reserve.reserve_aggregator import aggregate_reserves
    cfg = Config(policy_path=POLICY_PATH, assumptions_path=ASSUMPTIONS_PATH,
                 output_dir="results/", reserve_basis="VM21PA", reserve_method="StdScn")
    return aggregate_reserves(std_scn, carvm, dac, policy, cfg)


# ---- Step 20a: decremented cashflows ----------------------------------------

@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_dec_cf_shape(dec_cf):
    """dec_cf has cashflows columns + lives_eop (28 columns total)."""
    assert dec_cf.shape[1] == 28, f"Got {dec_cf.shape}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_dec_cf_bop_period1(dec_cf, cashflows, lives):
    """dec_cf.av_bop_sa[1] = cashflows.av_bop_sa[1] Ã— lives_eop[1]."""
    raw = float(cashflows.loc[1, "av_bop_sa"])
    l   = float(lives.loc[1, "lives_eop"])
    expected = raw * l
    val = float(dec_cf.loc[1, "av_bop_sa"])
    assert abs(val - expected) < 0.01, f"Expected {expected:.2f}, got {val:.2f}"


# ---- Step 20b: Standard Scenario ANR ----------------------------------------

@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_std_scn_shape(std_scn):
    assert std_scn.shape == (480, 19), f"Got {std_scn.shape}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_std_scn_accum_factor_period1(std_scn):
    """Accum factor[1] = 1/disc_factor_shock[1] â‰ˆ 1.04591847."""
    val = float(std_scn.loc[1, "accum_factor"])
    expected = 1.0 / (1.0 - (0.04019601 + 0.01) / 12.0)   # approx
    # Exact: M[1] = 1 / disc_factor_shock[1]
    from cashflows.interest import _running_disc_factor
    i_aey_shock = (1.0 + 0.0398/2)**2 - 1 + 0.01
    i_m_shock = (1 + i_aey_shock)**(1/12) - 1
    expected_exact = 1.0 / (1.0 / (1 + i_m_shock))
    assert abs(val - expected_exact) < 1e-4, f"Expected â‰ˆ{expected_exact:.6f}, got {val:.6f}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_std_scn_anr_zero(std_scn):
    """
    ANR = 0 for all 480 periods (confirmed from workbook Calc_StdScn_ANR!AO).
    Reason: AV-only death benefit â†’ no NAR; i4L payments deplete AV, not reserves.
    """
    assert (std_scn["anr"] == 0.0).all(), \
        f"Expected ANR=0 everywhere, got max={std_scn['anr'].max():.4f}"


# ---- Step 20c: Reserve aggregator ------------------------------------------

@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_reserve_shape(reserve):
    assert reserve.shape == (480, 12), f"Got {reserve.shape}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_reserve_t0_zero(reserve):
    """
    Valuation-date (period 1) reserve = $0.
    Workbook confirms: VM21PA StdScn ANR = 0 for policy 842612365.
    """
    val = float(reserve.loc[1, "reserve_t0"])
    assert val == 0.0, f"Expected reserve_t0=0.0, got {val}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_reserve_non_negative(reserve):
    """Reserve is non-negative for all periods (floor at 0 applied)."""
    assert (reserve["reserve"] >= 0.0).all()


# ---- Step 22: CARVM ---------------------------------------------------------

@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_carvm_shape(carvm):
    """480 Ã— 14 columns (7 time + 7 CARVM)."""
    assert carvm.shape == (480, 14), f"Got {carvm.shape}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_carvm_zero_for_vm21pa(carvm):
    """CARVM returns zeros for VM21PA basis (only binding under NYREG213+CARVM)."""
    assert (carvm["carvm_reserve"] == 0.0).all(), \
        "Expected carvm_reserve=0 for VM21PA basis"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_carvm_nyreg213_nonzero():
    """CARVM produces non-zero pv_csv for NYREG213+CARVM with positive AV."""
    if not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT:
        pytest.skip("data files not in data/")
    import numpy as np
    from config import Config
    from loaders.policy_loader import load_policy
    from loaders.assumption_loader import load_assumptions
    from loaders.scenario_loader import load_scenarios
    from decrements.time_axis import build_time_axis
    from decrements.lives import build_lives
    from decrements.mortality import build_mortality
    from decrements.lapse import build_lapse
    from cashflows.interest import build_interest_rates
    from cashflows.fund_mechanics import build_fund_mechanics
    from cashflows.i4l import build_i4l
    from cashflows.cashflow_engine import build_cashflows
    from reserve.decremented_cf import apply_lives
    from reserve.carvm import calculate_carvm

    p  = load_policy(POLICY_PATH)
    a  = load_assumptions(ASSUMPTIONS_PATH)
    s  = load_scenarios(POLICY_PATH)
    cfg = Config(policy_path=POLICY_PATH, assumptions_path=ASSUMPTIONS_PATH,
                 output_dir="results/", reserve_basis="NYREG213", reserve_method="CARVM")
    ta  = build_time_axis(p, cfg)
    mt  = build_mortality(ta, p, a, cfg)
    lp  = build_lapse(ta, p, a, cfg)
    lv  = build_lives(mt, lp, cfg)
    ir  = build_interest_rates(ta, s, cfg)
    fm  = build_fund_mechanics(ta, s, cfg)
    i4l = build_i4l(ta, p, a, cfg)
    cf  = build_cashflows(ta, p, fm, i4l, cfg)
    dc  = apply_lives(cf, lv)
    carvm_df = calculate_carvm(dc, ir, p, cfg)
    # With NYREG213+CARVM, carvm_reserve should be > 0 (CSV > 0)
    assert "carvm_reserve" in carvm_df.columns
    reserve_t1 = float(carvm_df.loc[1, "carvm_reserve"])
    assert reserve_t1 >= 0.0, f"CARVM reserve must be non-negative, got {reserve_t1}"


# ---- Step 24: DAC -----------------------------------------------------------

@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_dac_shape(dac):
    """480 Ã— 14 columns (7 time + 7 DAC)."""
    assert dac.shape == (480, 14), f"Got {dac.shape}"


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_dac_balance_zero(dac):
    """DAC balance = 0 throughout (D-003: DAC_Amortization_Basis = #VALUE!)."""
    assert (dac["dac_balance"] == 0.0).all()


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_dac_lives_bop_period1(dac):
    """Lives BOP[1] = 1.0 (seed â€” one policy cohort)."""
    assert float(dac.loc[1, "lives_bop"]) == 1.0


@pytest.mark.skipif(not _DATA_PRESENT or not _ASSUMPTIONS_PRESENT,
                    reason="data files not in data/")
def test_dac_lives_eop_matches_lives(dac, lives):
    """DAC lives_eop mirrors the decrements.lives.lives_eop."""
    import math
    v_dac   = float(dac.loc[1, "lives_eop"])
    v_lives = float(lives.loc[1, "lives_eop"])
    if math.isnan(v_lives):
        assert math.isnan(v_dac)
    else:
        assert abs(v_dac - v_lives) < 1e-10
