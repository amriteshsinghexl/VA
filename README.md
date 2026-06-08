# Abc_corp VA Python Valuation Model

Reproduces `VA_VT_Masked_V2_for Sandbox_NB.xlsx` reserve outputs in Python.  
Test policy: **842612365** (LMFR5, VM21PA, AV = $1,579,907.85, valuation 2025-06-30).

---

## How to Run

```bash
# from abc_corp_va/ directory in VS Code terminal
python run.py
```

With options:
```bash
python run.py --reserve-basis NYREG213 --reserve-method CARVM
python run.py --output-dir results/run2/ --months 480
```

**Output:** `results/abc_corp_va_output.xlsx` â€” 16 sheets, one per layer (see below).

---

## Folder Structure

```
abc_corp_va/
â”œâ”€â”€ run.py                  â† single entry point
â”œâ”€â”€ config.py               â† Config dataclass (basis, method, paths)
â”œâ”€â”€ data/                   â† INPUT FILES (not in git)
â”‚   â”œâ”€â”€ Input_PolicyDataRaw.xlsx
â”‚   â””â”€â”€ Assumptions_Extracted.xlsx
â”œâ”€â”€ results/                â† OUTPUT FILES (created on run)
â”‚   â””â”€â”€ abc_corp_va_output.xlsx
â”‚
â”œâ”€â”€ loaders/                â† Read-only data ingestion
â”‚   â”œâ”€â”€ policy_loader.py    â† policy fields from row 1/2 of Input_PolicyDataRaw
â”‚   â”œâ”€â”€ assumption_loader.pyâ† 72 assumption tables from Assumptions_Extracted
â”‚   â”œâ”€â”€ scenario_loader.py  â† ESG scenario (future 600m + historic 120m)
â”‚   â””â”€â”€ warnings.py         â† ModelWarning registry
â”‚
â”œâ”€â”€ decrements/             â† Mortality, lapse, lives
â”‚   â”œâ”€â”€ time_axis.py        â† 480-period projection spine
â”‚   â”œâ”€â”€ mortality.py        â† UDD monthly q, improvement multiplier
â”‚   â”œâ”€â”€ lapse.py            â† ITM Ã— SC-flag lookup, geometric monthly
â”‚   â””â”€â”€ lives.py            â† BOP/EOP recurrence
â”‚
â”œâ”€â”€ cashflows/              â† Per-unit AV projection
â”‚   â”œâ”€â”€ interest.py         â† BEYâ†’AEYâ†’monthlyâ†’disc_factor (+ 100bps shock)
â”‚   â”œâ”€â”€ fund_mechanics.py   â† Monthly growth factors (1+r)^(1/12)âˆ’1
â”‚   â”œâ”€â”€ sep_acct.py         â† Sep account waterfall: BOPâ†’M&Eâ†’IMFâ†’growthâ†’EOP
â”‚   â”œâ”€â”€ i4l.py              â† i4L rider: AP timing, discount U, annuity V/W
â”‚   â”œâ”€â”€ benefit_base.py     â† GMDB/GMWB guarantee bases
â”‚   â”œâ”€â”€ charges.py          â† Charge rate registry (GIB, i4L, M&E, suppressor)
â”‚   â”œâ”€â”€ withdrawals.py      â† Guaranteed income withdrawals
â”‚   â”œâ”€â”€ fixed_acct.py       â† Fixed account (zero for test policy)
â”‚   â””â”€â”€ cashflow_engine.py  â† Integrated loop: AV â†’ charges â†’ EOP per period
â”‚
â”œâ”€â”€ reserve/                â† Discounting and reserve calculation
â”‚   â”œâ”€â”€ decremented_cf.py   â† Multiply cashflows Ã— lives_eop (ONE place only)
â”‚   â”œâ”€â”€ std_scn_anr.py      â† VM21PA StdScn ANR (shocked rates, accumulated)
â”‚   â”œâ”€â”€ carvm.py            â† CARVM: max PV(CSV) across all future periods
â”‚   â”œâ”€â”€ dac.py              â† DAC amortisation (zero for test policy, D-003)
â”‚   â””â”€â”€ reserve_aggregator.pyâ† Final reserve = max(0, ANR) or CARVM by basis
â”‚
â”œâ”€â”€ output/
â”‚   â””â”€â”€ writer.py           â† Writes all DataFrames to Excel sheets
â”‚
â”œâ”€â”€ tests/
â”‚   â””â”€â”€ test_policy_842612365.py â† 137 tests (run: pytest tests/)
â”‚
â””â”€â”€ DISCREPANCIES.md        â† D-001â€¦D-016: workbook vs TMD divergences
```

---

## Output Sheets

| Sheet | What's in it |
|---|---|
| `00_Policy_Summary` | Key policy fields + final reserve |
| `01_Time_Axis` â†’ `04_Lives` | Decrements layer |
| `05_Interest_Rates` â†’ `09_Cashflow_Engine` | Cashflows layer |
| `10_Dec_Cashflows` â†’ `14_Reserve_Summary` | Reserve layer |
| `Warnings` | All ModelWarnings raised during the run |

---

## How to Change Things

| What to change | Where |
|---|---|
| Reserve basis / method | `--reserve-basis` / `--reserve-method` args, or edit `config.py` defaults |
| Projection months | `--months N` arg |
| Add a new charge type | `cashflows/charges.py` â†’ add rate; `cashflows/cashflow_engine.py` â†’ apply it |
| Fix masked mortality tables | Replace `data/Assumptions_Extracted.xlsx` with live version â†’ D-015, D-016 go away |
| Fix i4L payments (currently 0) | Same â€” live mortality tables enable W â†’ current_payment |
| Add a new reserve basis | `reserve/std_scn_anr.py` for new ANR variant; dispatch in `reserve_aggregator.py` |
| Add a second policy | Call each module with the new policy dict; the functions are all stateless |
| Change output columns | Edit the relevant `build_*()` function; the writer picks up all columns automatically |

---

## Key Known Limitations (Sandbox Data)

| Code | Issue | Impact |
|---|---|---|
| D-015 | `VM21PA_BaseMortality_Single` uses RAND()/10 | Mortality q values are meaningless |
| D-016 | `All_i4L_MortalityTables` truncated | i4L payments = 0; W = NaN |
| D-003 | `DAC_Amortization_Basis = #VALUE!` | DAC balance = 0 |
| D-014 | ITM/SC flag held static | Inaccurate for policies with active SC |

**Fix:** Replace `data/Assumptions_Extracted.xlsx` with the live (unmasked) version.  
The 2 skipped tests in the test suite will then pass automatically.

---

## Quick Test

```bash
pytest tests/                          # 137 pass, 2 skip
pytest tests/ -k "interest or lapse"  # run specific steps
```

---

## Project Files â€” What to Keep

The full project lives under `VA Model/`. Here is what each item is:

```
VA Model/
â”œâ”€â”€ abc_corp_va/                        â† THE MODEL â€” keep everything inside
â”œâ”€â”€ VA_VT_Masked_V2_for Sandbox_NB.xlsxâ† keep â€” source workbook for verification
â”œâ”€â”€ TMD_Abc_corp_VA_Final.docx          â† keep â€” technical spec (reference only)
â”‚
â”‚   â”€â”€ everything below is dev scratch, safe to delete â”€â”€
â”œâ”€â”€ Assumptions_Extracted.xlsx         â† delete â€” duplicate (copy already in abc_corp_va/data/)
â”œâ”€â”€ extract_data.py                    â† delete â€” one-off extraction script
â”œâ”€â”€ extract_output.txt                 â† delete â€” scratch output
â”œâ”€â”€ output.txt                         â† delete â€” scratch output
â”œâ”€â”€ sheet_summary.txt                  â† delete â€” scratch output
â”œâ”€â”€ tmd_*.txt                          â† delete â€” TMD text extracts from build phase
â”œâ”€â”€ tmd_unpacked/                      â† delete â€” unpacked TMD folder from build phase
â””â”€â”€ C:Usersvmuser... files             â† delete â€” garbled temp files
```

**The model is fully self-contained inside `abc_corp_va/`.**  
The data files the model reads are already copied to `abc_corp_va/data/` â€” nothing outside that folder is needed at runtime.
