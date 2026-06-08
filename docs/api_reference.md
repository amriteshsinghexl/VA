# VA — Express API Reference

The FIA UI (Express server on port 3000) exposes all endpoints used to run and
monitor the VA model.  The VA model is now run directly as a subprocess; no
separate FastAPI backend is required.

---

## Run VA model

### `POST /api/run`

Submit a model run for any product.  For VA, Express spawns `run.py` directly.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `product` | string | yes | `"VA"` |
| `runType` | string | no | `"portfolio"` (default) or `"single"` |
| `scenarioId` | string | no | Policy ID — required when `runType="single"` |
| `months` | string \| number | no | Projection months (default `480`) |
| `mode` | string | no | `"summary"` or `"per_policy"` — informational only |

**Example — run all policies (default)**
```json
{ "product": "VA", "runType": "portfolio", "months": "480" }
```

**Example — run single policy**
```json
{ "product": "VA", "runType": "single", "scenarioId": "842612365", "months": "480" }
```

**Command spawned by Express**
```
py C:\projects\VA\run.py
    --policy-path      C:\projects\VA\data\Input_PolicyDataRaw.xlsx
    --assumptions-path C:\projects\VA\data\Assumptions_Extracted.xlsx
    --output-dir       C:\projects\VA\results
    [--policy-id       <scenarioId>]
    [--months          <months>]
```

**Response 200**
```json
{ "runId": "3fa85f64-5717-4562-b3fc-2c963f66afa6" }
```

**Error responses**

| Status | Cause |
|---|---|
| 404 | `run.py` not found in `C:\projects\VA` |
| 400 | `runType=single` but no `scenarioId` supplied |

---

## Stream run output

### `GET /api/run/:runId/stream`

Server-Sent Events stream.  Late-joining clients receive all buffered lines first.

**Event format**

```
data: {"line": "[ 2/15] Policy loader ..."}
data: {"line": "[stderr] some warning"}
data: {"done": true, "exitCode": 0}
```

Line colouring applied by the terminal panel:
- Lines starting with `[stderr]` or `[error]` → red
- Lines starting with `=` → yellow bold (step banners)
- All others → green

---

## Run status

### `GET /api/run/:runId/status`

Returns the current state and full buffered output.

**Response 200**
```json
{
  "runId": "3fa85f64-...",
  "status": "completed",
  "exitCode": 0,
  "lineCount": 142,
  "output": ["[ 1/15] Config ...", "..."],
  "elapsedMs": 5140
}
```

`status` values: `running` → `completed` | `failed`

---

## VA Assumptions (in-app editor)

Six endpoints expose `Assumptions_Extracted.xlsx` to the browser-based editor at `/va-assumptions`.
See [va-assumptions-api.md](../../Updated-FIA-Validation-Tool-UI/docs/va-assumptions-api.md) for full
reference.  Summary:

| Method | Path | Action |
|---|---|---|
| `GET` | `/api/va/assumptions/sheets` | List all sheet names |
| `GET` | `/api/va/assumptions/download` | Download the full `.xlsx` file |
| `GET` | `/api/va/assumptions/sheet/:sheetName` | Get headers + rows for one sheet |
| `POST` | `/api/va/assumptions/sheet/:sheetName` | Save (overwrite) one sheet |
| `POST` | `/api/va/assumptions/sheets` | Add a new empty sheet |
| `DELETE` | `/api/va/assumptions/sheet/:sheetName` | Delete a sheet |

---

## Open file / folder

### `POST /api/open-file`

Opens a file or folder using the Windows default application (`start ""`).
Used by the **Data View** and **Reports → Open Results Folder** ribbon buttons when VA is selected.
The **Assumptions** ribbon button now navigates to `/va-assumptions` instead.

**Request body**

| Field | Type | Description |
|---|---|---|
| `filePath` | string | Absolute Windows path to file or folder |

**Examples**

```json
{ "filePath": "C:\\projects\\VA\\data\\Input_PolicyDataRaw.xlsx" }
{ "filePath": "C:\\projects\\VA\\results" }
```

**Response 200**
```json
{ "success": true }
```

The response is returned immediately; the OS opens the file asynchronously.

---

## Product discovery

### `GET /api/products`

Scans `C:\projects\` for subdirectories and returns them as the product list.

**Response 200**
```json
{
  "products": [
    { "id": "UL", "label": "UL" },
    { "id": "VA", "label": "VA" }
  ]
}
```

---

## Legacy FastAPI backend

`C:\projects\VA\start_backend.py` launches a FastAPI server on port 8001 that
was previously used by the FIA UI.  It is **no longer required** — the FIA UI
spawns `run.py` directly.  The FastAPI backend can still be used for standalone
API access; its own documentation is unchanged in `api_reference.md` (v1 routes).
