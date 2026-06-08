# Running the VA Model

## Prerequisites

```bash
cd C:\projects\VA
pip install -r requirements.txt
```

## Run from the FIA UI

```bash
cd C:\projects\Updated-FIA-Validation-Tool-UI
npm run dev
```

Open **http://localhost:3000**, select **VA** from the product dropdown, configure
Run Type / Analysis Mode, then click **Run VA Model**.

The Express server spawns `run.py` directly â€” **no separate backend process is needed**.

## Run from the command line

```bash
cd C:\projects\VA

# Default run (first policy, VM21PA, StdScn, 480 months)
py run.py

# Single policy by ID
py run.py --policy-id 842612365

# Custom projection horizon
py run.py --months 240

# Custom reserve basis / method
py run.py --reserve-basis NYREG213 --reserve-method CARVM

# Explicit file paths
py run.py --policy-path data/Input_PolicyDataRaw.xlsx \
          --assumptions-path data/Assumptions_Extracted.xlsx \
          --output-dir results/
```

> **Note:** use `py` (Windows Python Launcher) â€” `python` maps to a Store stub on
> this machine and will fail.

## CLI arguments (all optional)

| Argument | Default | Description |
|---|---|---|
| `--policy-path` | `data/Input_PolicyDataRaw.xlsx` | Input policy Excel file |
| `--assumptions-path` | `data/Assumptions_Extracted.xlsx` | Assumptions Excel file |
| `--output-dir` | `results/` | Output directory |
| `--output-file` | auto (`abc_corp_va_<policy_id>.xlsx`) | Override output filename |
| `--reserve-basis` | `VM21PA` | `VM21PA` \| `VM21CA` \| `NYREG213` \| `GAAPDAC` \| `CAPITAL` |
| `--reserve-method` | `StdScn` | `StdScn` \| `CARVM` \| `OptionValueFloor` |
| `--months` | `480` | Projection months (1â€“1080) |
| `--policy-id` | first row | Policy number to run (e.g. `842612365`) |

## Input / output locations

| Purpose | Path |
|---|---|
| Policy data | `C:\projects\VA\data\Input_PolicyDataRaw.xlsx` |
| Assumptions | `C:\projects\VA\data\Assumptions_Extracted.xlsx` |
| Results | `C:\projects\VA\results\abc_corp_va_<policy_id>.xlsx` |

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `PYTHON_EXEC` | `py` | Python executable used by the Express server to spawn `run.py` |
| `PRODUCTS_DIR` | `C:\projects` | Root folder scanned for product subfolders |
