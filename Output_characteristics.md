# Output Characteristics â€” Sheet-by-Sheet Guide

Explains what each sheet in `results/abc_corp_va_output.xlsx` calculates,
where decrements are applied, where present values are computed, and what
feeds the final reserve.

---

## Layer 1 â€” Inputs (no calculation)

### `00_Policy_Summary`
Raw policy fields + run configuration. No calculation â€” just what was read
from the input files. Contains the final `reserve_t0` at the top for quick reference.

### `01_Time_Axis`
Generates the 480-period projection calendar: dates, policy year, policy month,
attained age. Every other sheet uses this as its time spine.

---

## Layer 2 â€” Decrements (who survives each period)

### `02_Mortality`
Computes `q_monthly` â€” probability of dying in each month.
Uses the VM21PA base mortality table, improvement scale, age shift, and PAD multiplier.
Formula: UDD monthly conversion of the annual rate.
```
q_monthly = (q_annual / 12) / (1 âˆ’ (mâˆ’1)/12 Ã— q_annual)
```

### `03_Lapse`
Computes `q_lapse_monthly` â€” probability of surrendering each month.
Looks up the annual lapse rate from the VM21PA lapse table using ITM Ã— SC_flag,
then converts to monthly via geometric compounding:
```
q_lapse_monthly = 1 âˆ’ (1 âˆ’ q_lapse_annual)^(1/12)
```

### `04_Lives`
âš ï¸ **First decrement application.**
Combines mortality + lapse into a single surviving cohort:
```
lives_bop[1]   = 1.0  (seed â€” one cohort at valuation)
lives_eop[t]   = lives_bop[t] Ã— (1 âˆ’ q_mort[t]) Ã— (1 âˆ’ q_lapse[t])
lives_bop[t+1] = lives_eop[t]
```
Answers: "Of the original cohort, what fraction is still in force at end of period t?"

---

## Layer 3 â€” Per-Unit Cashflows (1 starting life, no decrement applied yet)

### `05_Interest_Rates`
Converts scenario BEY (Bond Equivalent Yield) rates to monthly discount factors:
```
BEY% â†’ AEY = (1 + BEY/2)Â² âˆ’ 1
     â†’ i_monthly = (1 + AEY)^(1/12) âˆ’ 1
     â†’ disc_factor        (unshocked â€” used in CARVM)
     â†’ disc_factor_shock  (+100bps at AEY level â€” used in StdScn ANR)
```

### `06_Fund_Mechanics`
Monthly equity growth factors per fund from the ESG scenario:
```
growth_factor[t] = (1 + EQ_Growth[t] / 100)^(1/12) âˆ’ 1
```
No AV here â€” just the rate of return each period for each of the 6 funds.

### `07_Sep_Acct`
Per-unit AV waterfall for all 6 separate-account funds:
```
BOP â†’ M&E charge â†’ IMF charge â†’ Ã— growth_factor â†’ EOP
```
Still per-unit (1 starting life). Charges reduce AV before growth is applied.
Also shows per-fund breakdown (av_bop_f1â€¦f6, av_eop_f1â€¦f6) and aggregate totals.

### `08_i4L_Rider`
Annuity factor engine for the i4L guaranteed income rider.
- **AP timing**: M (payment start month), N (AP date index), O (AP remaining), P (AP end age)
- **Discount factor U[t]**: `U[t] = U[t-1] / (1+AIR)^(1/12)` using effective annual AIR = 4%
- **V[t]** = AP annuity factor â€” sum of U over remaining access-period months Ã· 12.
  No mortality; payments are guaranteed during the access period.
- **W[t]** = Post-AP life annuity factor â€” probability-weighted PV of income after AP ends.
  Requires i4L mortality tables (currently NaN â€” D-016).
- Charge stubs (GIB, i4L): set to 0 until the cashflow engine provides the AV.

### `09_Cashflow_Engine`
âš ï¸ **Full integrated per-unit cashflow loop.**
This is where all modules come together each period in sequence:
```
Period t:
  BOP AV    = EOP AV[t-1]  (seed: initial fund AVs from Fund_Info)
  at_cme    = BOP Ã— (1 âˆ’ M&E/12) Ã— (1 âˆ’ IMF/12) Ã— (1 + growth_factor)
  GIB       = 0.004/12 Ã— at_cme           (suppressed under NYREG213+CARVM)
  i4L       = 0.005/12 Ã— at_cme           (suppressed under NYREG213+CARVM)
  withdrawal = i4l.monthly_payment         (from 08_i4L_Rider; 0 until live tables)
  EOP AV    = max(0, at_cme âˆ’ GIB âˆ’ i4L âˆ’ withdrawal)
```
Output is still **per-unit** (undecremented â€” one starting life, no cohort scaling yet).

---

## Layer 4 â€” Reserve (apply decrements + discount to get present values)

### `10_Dec_Cashflows`
âš ï¸ **Second and final decrement application.**
Multiplies every cashflow column from sheet 09 by `lives_eop` from sheet 04:
```
dec_cf[col][t] = cashflow[col][t] Ã— lives_eop[t]
```
Converts "per 1 starting life" â†’ "for the actual surviving cohort."
**This is the only place lives weighting is applied** â€” no other sheet multiplies by lives.

### `11_StdScn_ANR`
âš ï¸ **Present value calculation using shocked interest rates (+100bps).**
Accumulates the decrement-weighted fund value and charges forward using
the shocked discount factor from sheet 05:
```
N[t]           = dec_cf.av_eop_sa[t]            (lives-weighted AV)
X[t]           = N[t] Ã— (1 / disc_factor_shock[t])  (accumulated to t=0)
Accum_ME[t]    = Accum_ME[t-1] Ã— (1 + i_shock_monthly) + ME_charge[t]
Accum_IMF[t]   = same pattern
Accum_LB[t]    = GIB + i4L charges, accumulated with interest
net_rev_cf[t]  = (Accum_ME + Accum_IMF + Accum_LB) âˆ’ guaranteed_benefit_costs
ANR[t]         = max(0, âˆ’net_rev_cf[t])
```
For this policy: **ANR = 0** throughout (charges exceed guaranteed benefit costs â€”
AV-only death benefit means no net amount at risk; i4L payments are funded from AV).

### `12_CARVM`
âš ï¸ **Present value using unshocked interest rates** (binding only for NYREG213+CARVM).
At each period, computes the PV of the policyholder electing to surrender:
```
pv_csv[t]      = CSV[t] Ã— disc_factor[t]          (unshocked)
pv_annuity[t]  = annuity_benefit[t] Ã— disc_factor[t]  (0 for option A)
pv_max[t]      = max(pv_csv[t], pv_annuity[t])
CARVM_reserve  = backward running max of pv_max[]
```
For this policy (VM21PA basis): all zeros â€” CARVM is not the binding reserve.
Activates for NYREG213+CARVM runs.

### `13_DAC`
GAAP LDTI DAC amortisation schedule.
Shows lives progression (BOP, deaths, lapses, EOP) and the DAC balance each period.
For this policy: **DAC = 0** â€” Policy_Info!C107 = #VALUE! (D-003).

### `14_Reserve_Summary`
âš ï¸ **Final binding reserve selection.**
Picks the reserve from whichever sheet is relevant for the configured basis:
```
VM21PA  + StdScn  â†’  reserve[t] = max(0, ANR from sheet 11)
NYREG213 + CARVM  â†’  reserve[t] = max(0, CARVM from sheet 12)
GAAPDAC           â†’  reserve[t] = max(0, ANR) + DAC balance from sheet 13
```
`reserve_t0` = reserve at period 1 (valuation date) = **the balance sheet number**.

### `Warnings`
All `ModelWarning` messages raised during the run.
Key warnings for this sandbox run:
- D-015: VM21PA base mortality uses RAND()/10 (meaningless values until live tables loaded)
- D-016: i4L mortality table truncated (i4L payments = 0; W = NaN)
- D-003: DAC basis = #VALUE! (DAC = 0)

---

## Calculation Flow Diagram

```
INPUTS / RATES             DECREMENTS              PER-UNIT CASHFLOWS
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€             â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€              â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
01 Time Axis  â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
05 Int Rates  â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”   â”‚
                           02 Mortality â”€â”                     â”‚   â”‚
                           03 Lapse     â”€â”´â”€â†’ 04 Lives          â”‚   â”‚
                                              (qÃ—q each period) â”‚   â”‚
                                                    â”‚           â”‚   â”‚
                                            lives_eop           â”‚   â”‚
                                                    â”‚           â”‚   â”‚
                                    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜           â”‚   â”‚
06 Fund Mechanics  â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”   â”‚                           â”‚   â”‚
08 i4L Rider       â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â†’â”‚  09 Cashflow Engine       â”‚   â”‚
                                â”‚   â”‚  (per-unit AV loop)       â”‚   â”‚
07 Sep Acct    (standalone) â”€â”€â”€â”€â”˜   â”‚          â”‚                â”‚   â”‚
                                    â”‚          â†“                â”‚   â”‚
                                    â””â”€â”€â†’ 10 Dec Cashflows       â”‚   â”‚
                                         (Ã— lives_eop)          â”‚   â”‚
                                                â”‚               â”‚   â”‚
                    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜               â”‚   â”‚
                    â†“                                           â”‚   â”‚
             11 StdScn ANR â†â”€â”€ shocked disc_factor â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜   â”‚
             12 CARVM      â†â”€â”€ unshocked disc_factor                â”‚
             13 DAC        â†â”€â”€ lives from 04                        â”‚
                    â”‚                                               â”‚
                    â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â†’ 14 Reserve Summary             â”‚
                                     reserve_t0 = final output      â”‚
                                                                     â”‚
                                     (all sheets use time spine) â”€â”€â”€â”˜
```

---

## Which Sheets Feed the Final Reserve

| Sheet | What it contributes | Used by |
|---|---|---|
| `04_Lives` | `lives_eop[t]` â€” cohort survival | `10_Dec_Cashflows` |
| `05_Interest_Rates` | `disc_factor_shock` â€” shocked PV factors | `11_StdScn_ANR` |
| `05_Interest_Rates` | `disc_factor` â€” unshocked PV factors | `12_CARVM` |
| `09_Cashflow_Engine` | `av_eop_sa[t]` â€” per-unit AV each period | `10_Dec_Cashflows` |
| `10_Dec_Cashflows` | `av_eop_sa Ã— lives` â€” cohort-weighted AV | `11_StdScn_ANR` |
| `11_StdScn_ANR` | `anr[t]` â€” accumulated net revenue | `14_Reserve_Summary` |
| `12_CARVM` | `carvm_reserve[t]` â€” max PV surrender | `14_Reserve_Summary` |
| `13_DAC` | `dac_balance[t]` â€” DAC amortisation | `14_Reserve_Summary` |
| **`14_Reserve_Summary`** | **`reserve_t0`** â€” **final balance sheet reserve** | â€” |
