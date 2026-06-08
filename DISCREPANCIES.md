# DISCREPANCIES.md

Record of every place where the TMD specification diverges from the actual Excel workbook
`VA_VT_Masked_V2_for Sandbox_NB.xlsx`. **Implementation always follows the workbook.**

Format per entry:
- **§**: TMD section number
- **Workbook location**: tab + cell/range where the true formula lives
- **TMD says**: literal quote or description from the document
- **Workbook does**: observed formula / structure
- **Impact**: how this changes the Python implementation

---

## D-001 — Input_PolicyDataRaw row layout

- **§**: §3.2 (Policy Data Input)
- **Workbook location**: `Input_PolicyDataRaw` rows 1–4, column A onward
- **TMD says**: "shaped 4 rows × 243 columns. Row 1 is a header section, row 2 is a
  long-form descriptive label, row 3 carries the SQL field name (the lookup key), and
  row 4 onward carries one policy per row."
- **Workbook does**: Row 1 = SQL field names (`policy_number`, `issue_year`, …); Row 2 =
  policy data values (842612365 is in row 2); Row 3 = type-description labels
  ("Alpha Numeric (Text Form)", …); Row 4 = column-number indices (1, 2, 3, …).
- **Impact**: `policy_loader.py` must treat **row 1 as column headers** and **row 2 as
  the data row** (zero-based: header=0, data_row index=1). Do not look for data starting
  at row 4.

---

## D-002 — Assumptions_Extracted.xlsx sheet count

- **§**: §23.4 (Assumption Loader)
- **Workbook location**: `Assumptions_Extracted.xlsx` sheet list
- **TMD says**: "72 sheets" in the Assumptions file.
- **Workbook does**: Contains 73 sheets: `_README` (non-data documentation) plus 72
  data sheets that carry actual assumption tables.
- **Impact**: `assumption_loader.py` must skip the `_README` sheet and load the
  remaining 72 data sheets. No formula or numerical impact.

---

## D-003 — DAC_Amortization_Basis cell evaluates to #VALUE!

- **§**: §24 (edge cases)
- **Workbook location**: `Policy_Info!C107`
- **TMD says**: (no explicit mention of this error state)
- **Workbook does**: `Policy_Info!C107` (DAC_Amortization_Basis) returns `#VALUE!` for
  the test policy.
- **Impact**: `policy_loader.py` must catch `#VALUE!` / any Excel error on this cell,
  log a `ModelWarning`, and default the field to `None`. Reserve logic must handle
  `None` DAC basis gracefully.

---

## D-004 — RAND()/10 placeholders in Product Features tab

- **§**: §24 (edge cases / volatile cells)
- **Workbook location**: `Product Features!CO:CY`
- **TMD says**: (acknowledges RAND() volatility; these are placeholder markers)
- **Workbook does**: Cells in columns CO:CY contain `=RAND()/10` as explicit
  placeholders (not true model inputs).
- **Impact**: Any loader that reads these cells must detect the `RAND()/10` pattern,
  raise a `ModelWarning("RAND placeholder encountered — value not used")`, and never
  propagate the sampled value into calculations.

---

## D-005 — Stub period (Policy_Info!T15) permanently zeroed

- **§**: §5 (time axis / stub period)
- **Workbook location**: `Policy_Info!T15`
- **TMD says**: stub period formula `=MIN(DAY(IssueDate)/30,1)` — implies a non-zero
  value is possible.
- **Workbook does**: `=MIN(DAY(IssueDate)/30,1)*0` — the trailing `*0` permanently
  zeroes the stub period regardless of issue date.
- **Impact**: `time_axis.py` must set `stub_period = 0.0` unconditionally. Do not
  compute a proportional stub from the issue day. Preserve the formula structure (with
  `*0`) in comments for future activation.

---

## D-006 — CAPITAL basis lapse rate forced to zero

- **§**: §24.5.2 (CAPITAL basis special cases)
- **Workbook location**: Lapse engine columns under CAPITAL basis
- **TMD says**: (no explicit mention)
- **Workbook does**: When `Reserve_Basis = "CAPITAL"`, lapse rates are set to 0 across
  all lapse engines.
- **Impact**: `lapse.py` must check `config.reserve_basis == "CAPITAL"` and return
  zero for all lapse rates, logging a `ModelWarning` per §24.5.2.

---

## D-007 — NYREG213 + CARVM suppressor on all charges

- **§**: §14 (charges) and §22 (NYREG213)
- **Workbook location**: All charge columns in every Calc_ tab, e.g.
  `Calc_CARVM`, `Calc_StdScn_ANR`
- **TMD says**: "charges must be suppressed under NYREG213+CARVM"
- **Workbook does**: Formula pattern
  `*IF(Reserve_Basis="NYREG213",IF(Reserve_Method="CARVM",0,1),1)` applied to every
  charge cell.
- **Impact**: `cashflows/charges.py` must apply this two-level suppressor flag as a
  vectorised mask before any charge enters the cashflow engine.

---

## D-008 — No-lapse CARVM convention (Calc_Lapse_NYREG213!AL10 = 0)

- **§**: §9 (lapse engine) and §22 (NYREG213)
- **Workbook location**: `Calc_Lapse_NYREG213!AL10`
- **TMD says**: AL column carries dynamic lapse for NYREG213 basis.
- **Workbook does**: `Calc_Lapse_NYREG213!AL10` is forced to 0 when
  `Reserve_Method = "CARVM"` — i.e., the NYREG213 lapse engine's AL column is zeroed
  out under CARVM.
- **Impact**: `lapse.py` NYREG213 engine must override its AL-column result to 0.0
  whenever `config.reserve_method == "CARVM"`.

---

## D-011 — Workbook time axis has 1200 rows; Python model uses config.projection_months

- **§**: §5 (Time Axis) and §7 (time_axis.py)
- **Workbook location**: `Calc_StdScn_ANR` rows 10–1209; `Calc_CARVM` rows 10–1209
- **TMD says**: (implies `projection_months` rows of time axis)
- **Workbook does**: Both `Calc_StdScn_ANR` and `Calc_CARVM` contain exactly 1200 data
  rows = 100 calendar years of projection. The `Configuration` sheet cell `Months of
  Projection = 480` is not used to truncate the time axis.
- **Impact**: Python `time_axis.py` generates `config.projection_months` rows (default
  480). To exactly reproduce the workbook's 1200-row spine, set
  `projection_months=1200`. No numerical difference for the reserve calculation as
  cashflows beyond 480 months are zero for this policy.

---

## D-010 — Paste_ scenario tabs are output-staging areas, not ESG inputs

- **§**: §6 (Scenario Loader)
- **Workbook location**: `Paste_StdScn1`, `Paste_StdScn2`, `Paste_CARVM_PW`,
  `Paste_CARVM_NoPW`
- **TMD says**: "load the six Paste_ / ESG scenario tabs"
- **Workbook does**: `Paste_StdScn1` and `Paste_StdScn2` have only header rows (rows
  8–9) and no data rows. `Paste_CARVM_PW` and `Paste_CARVM_NoPW` are similarly empty.
  These tabs are *output* staging areas where AXIS model results are pasted before the
  Calc_ tabs consume them; they are empty in the masked sandbox workbook.
  The actual ESG scenario inputs live in `Input_Future Scenario` (24 variables × 600
  months) and `Input_Historic Scenario` (18 variables × 120 months).
- **Impact**: `scenario_loader.py` loads only `Input_Future Scenario` and
  `Input_Historic Scenario`. The four `Paste_*` tabs are ignored. No numerical impact
  for this single-policy sandbox; full AXIS integration would require populating them.

---

## D-009 — Incomplete source ranges in Assumptions_Extracted.xlsx

- **§**: §23.4 (Assumption Loader)
- **Workbook location**: `Assumptions_Extracted.xlsx` — `source_range` metadata field
  (row 2) for at least `All_i4L_MortalityAgeShift` and `VM21PA_PerPolicyExpenses`
- **TMD says**: (no explicit mention of source range completeness)
- **Workbook does**: Some sheets carry a `source_range` value ending in `"~"` (tilde),
  indicating the extraction was cut short and the true range extends further than
  recorded (e.g. `"'Misc Mappings'!C51:V54~"`).
- **Impact**: The `"~"` suffix is preserved as-is in `.attrs['meta']['source_range']`.
  No data is lost — all extracted rows are still loaded. The tilde is a documentation
  marker only and does not affect the data block. Downstream anchor-lookup code must
  strip the trailing `"~"` before parsing cell references.

---

---

## D-012 — NYREG213 mortality factor table name and column structure

- **§**: §8 (Mortality Engine)
- **Workbook location**: `Assumptions_Extracted.xlsx` — `NYREG213_MortalityFactor`
- **TMD says**: (implies same naming pattern as VM21PA mortality factor tables)
- **Workbook does**: The NYREG213 mortality factor table is named `NYREG213_MortalityFactor`
  (no `_Addition` suffix). Its columns are rider-type based: `Lifetime`, `NonLifetime`, `None`
  — **not** gender × GLB combinations (`WithGLB_Male`, etc.) as in `VM21PA_MortalityFactor_Addition`.
- **Impact**: `mortality.py` must use `NYREG213_MortalityFactor` as the table key for NYREG213
  basis and must map the policy's rider type to the correct column:
  `i4l_indicator='i4L'` → `'Lifetime'`; otherwise → `'None'`.

---

## D-013 — VM21PA_MortalityImprovement has no 'F' column

- **§**: §8 (Mortality Engine)
- **Workbook location**: `Assumptions_Extracted.xlsx` — `VM21PA_MortalityImprovement`
- **TMD says**: (implies gender-specific improvement scales for M and F)
- **Workbook does**: `VM21PA_MortalityImprovement` contains columns `M` and `U` only — no `F`
  column. Female policies must use `U` (unisex) for improvement scale lookup.
- **Impact**: `mortality.py` must fall back to column `U` when gender column `F` is absent in
  the improvement scale table. Current implementation returns NaN for female policies until
  the fallback is implemented.

---

---

## D-014 — VM21PA lapse SC-flag is static (simplification)

- **§**: §9 (Lapse Engine)
- **Workbook location**: `Calc_Lapse_VM21PA` columns related to surrender-charge period flag
- **TMD says**: SC period flag (1/2/3) is a running per-bucket count updated each projection step.
- **Workbook does**: Computes the SC period flag dynamically from the remaining surrender-charge
  bucket balances, which evolve as withdrawals and credits accrue during projection.
- **Impact**: `lapse.py` currently sets SC flag once at valuation date and holds it constant for
  all projection periods. For this test policy (all SC buckets = 0), the result is correct:
  SC flag = 3 for all periods. Policies with active surrender charges will produce incorrect
  SC flags in periods after the SC period expires. Full dynamic SC tracking is deferred to the
  cashflow engine integration step.

---

## D-015 — VM21PA_BaseMortality_Single masked with RAND()/10 floats, not DUMMY strings

- **§**: §8 (Mortality Engine)
- **Workbook location**: `Assumptions_Extracted.xlsx` — `VM21PA_BaseMortality_Single`
- **TMD says**: (implies masked cells should be detectable as placeholders)
- **Workbook does**: `VM21PA_BaseMortality_Single` columns F/M/U store `=RAND()/10`
  formulas. When Excel recalculates the workbook and `openpyxl` reads with
  `data_only=True`, each cell delivers a random float in [0, 0.1] that looks
  like a plausible annual mortality rate. There is no "[DUMMY placeholder]" text,
  so no `ModelWarning` is raised.
- **Impact**: `q_monthly` values produced by the mortality engine from this table
  are numerically present but meaningless (random per workbook recalculation).
  `lives_eop` is therefore a finite (but meaningless) number rather than NaN.
  No value from `VM21PA_BaseMortality_Single` should be used in production until
  live tables are populated. Contrast with sheets like `VM21CA_BaseMortality_Single`
  which use `[DUMMY placeholder RAND]` strings and do generate `ModelWarning`.
  D-004 covers the RAND()/10 float-masking convention in the Product Features tab;
  D-015 records its occurrence in the VM21PA mortality base table.

---

## D-016 — All_i4L_MortalityTables and All_i4L_MortalityAgeShift truncated in Assumptions_Extracted.xlsx

- **§**: §17 (i4L Rider Engine — Calc_i4L)
- **Workbook location**: `Assumptions_Extracted.xlsx` — `All_i4L_MortalityTables`, `All_i4L_MortalityAgeShift`
- **TMD says**: (implies full mortality tables available for i4L annuity factor pricing)
- **Workbook does**: Both tables carry a `source_range` ending in `~` (D-009 tilde convention),
  indicating the extraction was cut short. `All_i4L_MortalityTables` contains only metadata
  rows plus one data point; `All_i4L_MortalityAgeShift` contains only metadata rows.
  The full tables live in the main model workbook at `Assumptions!$BWK$7:$BWS$~` and
  `Assumptions!$BWG$7:$BWH$~` respectively.
- **Impact**: `i4l.py` cannot perform the mortality table lookup from Assumptions_Extracted.xlsx.
  Columns R (annual mortality), S (monthly mortality), T (survivorship), and W (post-AP
  annuity factor) will be NaN for all periods. The age shift defaults to 0 (instead of 2 for
  the test policy). V (AP annuity factor) is computed correctly because it uses only the
  discount factor U and requires no mortality. Confirmed workbook values for period 1:
  R=0.573084, S=0.068474, T=1.0, U=1.0, V=11.357842, W=0.494585 (age 77, Qi4LTbl1/M, AIR=4%).
  Enable full computation once live Assumptions tables are loaded.

---

*Last updated: Step 14 — i4L rider engine.*
*Additional discrepancies will be appended as each build step uncovers them.*
