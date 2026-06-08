# VA Model Architecture

## Overview

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  FIA UI  (React + Express  :3000)                        â”‚
â”‚                                                          â”‚
â”‚  InputsView        â†’  POST /api/run  (product=VA)       â”‚
â”‚  TopRibbon         â†’  POST /api/open-file (Data/Results)â”‚
â”‚  VAAssumptionsView â†’  /api/va/assumptions/*  (CRUD)     â”‚
â”‚  Terminal panel    â†  SSE stream /api/run/:id/stream    â”‚
â”‚                                                          â”‚
â”‚  Express spawns subprocess directly:                     â”‚
â”‚    py  C:\projects\VA\run.py  [args]                    â”‚
â”‚         stdout / stderr â†’ SSE â†’ browser terminal        â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                           â”‚ subprocess stdout/stderr
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  Abc_corp VA Model  (C:\projects\VA\)                     â”‚
â”‚                                                          â”‚
â”‚  run.py  â†’  15-step pipeline                            â”‚
â”‚    [1]  Config                                           â”‚
â”‚    [2]  Policy loader      â† data/Input_PolicyDataRaw.xlsxâ”‚
â”‚    [3]  Assumption loader  â† data/Assumptions_Extracted.xlsxâ”‚
â”‚    [4]  Scenario loader                                   â”‚
â”‚    [5]  Time axis                                         â”‚
â”‚    [6-8] Decrements (mortality, lapse, lives)            â”‚
â”‚    [9-11] Cashflows (interest, funds, i4L)               â”‚
â”‚    [12]  Cashflow engine                                  â”‚
â”‚    [13]  Reserve (StdScn / CARVM / DAC)                  â”‚
â”‚    [14]  Output writer  â†’  results/abc_corp_va_*.xlsx     â”‚
â”‚    [15]  Summary banner                                   â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

## Request / response flow

1. **UI** sends `POST /api/run` to Express with `product=VA`, `runType`, optional `scenarioId` (= policy ID), and `months`.
2. **Express** resolves fixed file paths and spawns: `py run.py --policy-path ... --assumptions-path ... --output-dir ... [--policy-id ...] [--months ...]`
3. **stdout/stderr** lines are captured and pushed line-by-line to the SSE job store.
4. **Browser terminal** consumes the SSE stream and renders output in real time.
5. When the process exits, Express sends `{ done: true, exitCode }` and closes the stream.

## Ribbon button file integration

When **VA** is the selected product, the top ribbon buttons behave as follows:

| Button | Behaviour |
|---|---|
| Data View | Opens `C:\projects\VA\data\Input_PolicyDataRaw.xlsx` via `POST /api/open-file` (OS default app) |
| Assumptions | Navigates to `/va-assumptions` â€” in-app multi-sheet editor |
| Reports â†’ Open Results Folder | Opens `C:\projects\VA\results\` via `POST /api/open-file` (Windows Explorer) |

`POST /api/open-file` executes `start "" "<path>"` via the Windows shell for files opened externally.
The Assumptions editor uses the `/api/va/assumptions/*` endpoints to read and write the workbook
without leaving the browser.

## Directory layout

```
C:\projects\VA\
â”œâ”€â”€ run.py                   â† CLI entry point (spawned by Express)
â”œâ”€â”€ config.py                â† Config dataclass
â”œâ”€â”€ data\
â”‚   â”œâ”€â”€ Input_PolicyDataRaw.xlsx      â† policy data (read by run.py)
â”‚   â””â”€â”€ Assumptions_Extracted.xlsx   â† 72 assumption tables (read by run.py)
â”œâ”€â”€ results\                 â† Output Excel files (written by run.py)
â”œâ”€â”€ docs\                    â† This documentation
â”œâ”€â”€ app\                     â† Legacy FastAPI backend (not used by FIA UI)
â””â”€â”€ start_backend.py         â† Legacy FastAPI launcher (not used by FIA UI)
```

## Run job lifecycle (Express side)

```
POST /api/run  â†’  creates RunJob { runId, status:"running", output:[], subscribers:Set }
                   spawns subprocess
                       â”‚ stdout line â†’ pushLine(job, line) â†’ broadcast to SSE subscribers
                       â”‚ stderr line â†’ pushLine(job, "[stderr] " + line)
                       â”” on close    â†’ finishJob(job, exitCode) â†’ send {done, exitCode}

GET /api/run/:runId/stream  â†’  SSE â€” replays buffered lines then live-streams
GET /api/run/:runId/status  â†’  JSON snapshot of job state
```
