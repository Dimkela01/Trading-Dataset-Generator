# AlphaForge

Trading dataset preparation platform — upload OHLCV or custom time-series data, transform columns, engineer features, generate labels, split temporally, and export train/test Parquet files with a standalone HTML report.

## Stack

- **Backend:** FastAPI, pandas, pandas-ta, pyarrow
- **Frontend:** React 18 + Vite, Recharts (wizard charts), terminal-inspired dark UI

## Install

```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

## Run

Terminal 1 — API (port 8000):

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Terminal 2 — UI (port 5173, proxies `/api` → backend):

```bash
cd frontend
npm run dev
```

Open http://localhost:5173

> Sessions are stored in memory. Restarting the backend clears uploaded data.

## Test upload (curl)

```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@sample_data/btc_1h.csv"
```

Select a single asset from a multi-symbol file:

```bash
curl -X POST http://localhost:8000/select_asset \
  -H "Content-Type: application/json" \
  -d '{"session_id":"<from-upload>","symbol_column":"symbol","symbol_value":"BTCUSDT"}'
```

## Tests

Install dev dependencies and run the test suite from the repo root:

```bash
pip install -r backend/requirements.txt -r requirements-dev.txt
pytest tests/ -v
```

Tests cover detection, transforms, features (including rejection paths), labeling framings, full pipeline splits, and API upload/preview/export.

## End-to-end flow

1. Upload `sample_data/btc_1h.csv` (or any CSV/Parquet with a timestamp column).
2. Review the data summary, then click **BEGIN PIPELINE**.
3. Walk through: Column Manager → Features → Labels → Train/Test Split.
4. Click **GENERATE DATASET** to download `alphaforge_export.zip` containing:
   - `train.parquet`
   - `test.parquet`
   - `metadata.json`
   - `report.html`

## Project structure

```
backend/
  main.py
  pipeline.py
  processors/   # detector, transformer, features, labeler, splitter, exporter
frontend/
  src/
    App.jsx
    components/
    api/client.js
sample_data/
  btc_1h.csv
```
