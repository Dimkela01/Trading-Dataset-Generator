import io
import uuid
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from pipeline import (
    _drop_incomplete_rows,
    df_to_preview_records,
    run_pipeline,
    warmup_offset,
)
from processors.detector import analyze
from processors.exporter import (
    build_metadata,
    build_zip,
    compute_label_distribution,
    generate_report_html,
)
from processors.labeler import apply_label

app = FastAPI(title="AlphaForge API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: dict[str, dict[str, Any]] = {}


class ColumnTransform(BaseModel):
    column: str
    transform: str = "none"
    params: dict = Field(default_factory=dict)


class FeatureConfig(BaseModel):
    type: str
    params: dict = Field(default_factory=dict)


class LabelConfig(BaseModel):
    method: str
    params: dict = Field(default_factory=dict)


class SplitConfig(BaseModel):
    method: str = "temporal"
    params: dict = Field(default_factory=dict)


class PipelineState(BaseModel):
    session_id: str
    column_transforms: list[ColumnTransform] = Field(default_factory=list)
    features: list[FeatureConfig] = Field(default_factory=list)
    label: LabelConfig | None = None
    split: SplitConfig = Field(default_factory=lambda: SplitConfig(method="temporal", params={"train_ratio": 0.8}))


class SelectAssetRequest(BaseModel):
    session_id: str
    symbol_column: str
    symbol_value: str


def _state_to_dict(state: PipelineState) -> dict:
    return state.model_dump()


def _get_session(session_id: str) -> dict:
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found. Please upload again.")
    return sessions[session_id]


def _read_upload(content: bytes, filename: str) -> pd.DataFrame:
    ext = filename.lower().split(".")[-1]
    buf = io.BytesIO(content)
    if ext in ("csv", "txt"):
        df = pd.read_csv(buf)
        if len(df.columns) == 1 and ";" in str(df.columns[0]):
            buf.seek(0)
            df = pd.read_csv(buf, sep=";")
        return df
    if ext in ("parquet", "pq"):
        return pd.read_parquet(buf, engine="pyarrow")
    raise HTTPException(status_code=415, detail="Unsupported file type. Use CSV or Parquet.")


def _upload_response(session_id: str, analysis: dict) -> dict:
    return {
        "session_id": session_id,
        **{k: v for k, v in analysis.items() if k not in ("ohlcv_map",)},
    }


def _price_context_from_session(session: dict) -> dict:
    return {
        "bid_column": session.get("bid_column"),
        "ask_column": session.get("ask_column"),
        "ohlcv_map": session.get("ohlcv_map", {}),
    }


def _update_session_from_analysis(session: dict, analysis: dict) -> None:
    session["timestamp_column"] = analysis.get("timestamp_column")
    session["ohlcv_map"] = analysis.get("ohlcv_map", {})
    session["bid_column"] = analysis.get("bid_column")
    session["ask_column"] = analysis.get("ask_column")
    session["has_order_book"] = analysis.get("has_order_book", False)
    session["analysis"] = analysis


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    filename = file.filename or "dataset.csv"
    content = await file.read()

    try:
        df = _read_upload(content, filename)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")

    analysis = analyze(df)
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "df": df,
        "df_raw": df.copy(),
        "filename": filename,
        "symbol_column": analysis.get("symbol_column"),
    }
    _update_session_from_analysis(sessions[session_id], analysis)

    return _upload_response(session_id, analysis)


@app.post("/select_asset")
async def select_asset(body: SelectAssetRequest):
    session = _get_session(body.session_id)
    df_raw = session.get("df_raw", session["df"])

    if body.symbol_column not in df_raw.columns:
        raise HTTPException(status_code=400, detail=f"Column '{body.symbol_column}' not found.")

    filtered = df_raw[df_raw[body.symbol_column].astype(str) == str(body.symbol_value)].copy()
    if filtered.empty:
        raise HTTPException(status_code=400, detail=f"No rows found for symbol '{body.symbol_value}'.")

    session["df"] = filtered
    session["selected_symbol"] = body.symbol_value

    analysis = analyze(filtered, skip_multi_asset_check=True)
    _update_session_from_analysis(session, analysis)

    return _upload_response(body.session_id, analysis)


@app.post("/preview")
async def preview(state: PipelineState):
    session = _get_session(state.session_id)
    state_dict = _state_to_dict(state)

    result, meta, err = run_pipeline(
        session["df"],
        state_dict,
        timestamp_col=session["timestamp_column"],
        ohlcv_map=session.get("ohlcv_map", {}),
        include_label=False,
        include_split=False,
        price_context=_price_context_from_session(session),
    )
    if err:
        raise HTTPException(status_code=400, detail=err)

    ts_col = session["timestamp_column"]

    # Live label preview: compute the label on the feature-engineered frame so
    # the wizard shows the label column, its class balance, and validates a
    # custom expression inline. A label failure (e.g. a bad custom expression)
    # is surfaced as a warning without discarding the column/feature preview.
    label_cfg = state_dict.get("label")
    labeled: pd.DataFrame | None = None
    label_error: str | None = None
    if label_cfg and label_cfg.get("method"):
        labeled, label_error = apply_label(
            result, label_cfg, _price_context_from_session(session)
        )

    # Show the frame the user will actually export: labeled when the label is
    # valid, otherwise the feature-only frame with the error surfaced below.
    display = labeled if (labeled is not None and not label_error) else result

    # Skip the leading indicator warm-up so the preview shows populated rows,
    # not a wall of NaNs. `final_row_count` is what export will actually write
    # (after warmup + forward-label rows are dropped), so the count is honest.
    offset = warmup_offset(display, ts_col)
    cleaned, _ = _drop_incomplete_rows(display, ts_col)
    label_cols = [c for c in display.columns if c.startswith("label")]

    response: dict[str, Any] = {
        "columns": list(display.columns.astype(str)),
        "row_count": len(result),
        "final_row_count": len(cleaned),
        "preview": df_to_preview_records(display.iloc[offset:]),
        "warmup_rows": offset,
        "features_added": meta.get("features_added", []),
        "label_columns": label_cols,
        "label_distribution": None,
        "label_is_classification": None,
        "label_row_count": None,
        "label_error": label_error,
    }

    if labeled is not None and not label_error:
        dist, is_classification = compute_label_distribution(labeled, label_cfg)
        response["label_distribution"] = dist
        response["label_is_classification"] = is_classification
        if label_cols:
            response["label_row_count"] = int(
                labeled[label_cols].notna().any(axis=1).sum()
            )

    return response


@app.post("/export")
async def export_dataset(state: PipelineState):
    session = _get_session(state.session_id)
    state_dict = _state_to_dict(state)

    result, meta, err = run_pipeline(
        session["df"],
        state_dict,
        timestamp_col=session["timestamp_column"],
        ohlcv_map=session.get("ohlcv_map", {}),
        include_label=True,
        include_split=True,
        price_context=_price_context_from_session(session),
    )
    if err:
        raise HTTPException(status_code=400, detail=err)

    train_df = meta["train_df"]
    test_df = meta["test_df"]
    label_dist, is_classification = compute_label_distribution(result, state_dict.get("label"))

    label_cols = [c for c in result.columns if c.startswith("label")]
    stats = {
        "total_rows": len(result),
        "train_rows": len(train_df),
        "test_rows": len(test_df),
        "feature_count": len([c for c in result.columns if c not in label_cols]),
        "label_distribution": label_dist,
        "label_columns": label_cols,
        "split_fold_used": meta.get("split_fold"),
        "rows_dropped_incomplete": meta.get("rows_dropped_incomplete", 0),
        "rows_before_clean": meta.get("rows_before_clean", len(result)),
    }

    metadata = build_metadata(state_dict, stats, session["filename"])
    report_html = generate_report_html(
        session["filename"],
        state_dict,
        train_df,
        test_df,
        result,
        session["timestamp_column"],
        label_dist,
        is_classification,
        rows_dropped=meta.get("rows_dropped_incomplete", 0),
    )

    zip_bytes = build_zip(train_df, test_df, metadata, report_html)

    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=alphaforge_export.zip"},
    )


@app.get("/health")
def health():
    return {"status": "ok"}
