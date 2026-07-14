from typing import Any

import numpy as np
import pandas as pd

from processors.transformer import apply_transforms
from processors.features import apply_features
from processors.labeler import apply_label
from processors.splitter import temporal_split, walk_forward_split


def _protected_columns(
    df: pd.DataFrame,
    ohlcv_map: dict,
    price_context: dict | None,
) -> set[str]:
    """Raw price/volume/bid/ask columns that later stages resolve by name.

    These must survive column transforms so RSI/MACD/labels can still find
    their price series (see transformer.apply_transforms)."""
    ctx = price_context or {}
    names = set(ohlcv_map.values())
    for key in ("bid_column", "ask_column"):
        if ctx.get(key):
            names.add(ctx[key])
    return {c for c in names if c in df.columns}


def _label_horizon(label_cfg: dict | None) -> int:
    """How many bars forward a label looks — used to embargo the split so
    train labels can't peek into the test set."""
    if not label_cfg:
        return 0
    params = label_cfg.get("params") or {}
    method = label_cfg.get("method")
    if method == "forward_return":
        return int(params.get("periods", params.get("T", 5)))
    if method == "triple_barrier":
        return int(params.get("max_periods", 10))
    return 0


def _sort_by_time(df: pd.DataFrame, timestamp_col: str | None) -> pd.DataFrame:
    """Guarantee ascending chronological order before any shift-based op.

    Every return/lag/label/split assumes row i precedes row i+1 in time. We sort
    on a parsed copy of the timestamp (stable, so equal timestamps keep their
    original order) without altering the exported column's dtype/formatting."""
    if not timestamp_col or timestamp_col not in df.columns:
        return df
    parsed = pd.to_datetime(df[timestamp_col], errors="coerce")
    order = parsed.sort_values(kind="stable").index
    return df.loc[order].reset_index(drop=True)


def run_pipeline(
    df: pd.DataFrame,
    state: dict[str, Any],
    *,
    timestamp_col: str | None,
    ohlcv_map: dict | None = None,
    include_label: bool = True,
    include_split: bool = True,
    price_context: dict | None = None,
) -> tuple[pd.DataFrame | None, dict[str, Any] | None, str | None]:
    meta: dict[str, Any] = {"features_added": []}
    ohlcv_map = ohlcv_map or {}

    working = df.copy()
    working = _sort_by_time(working, timestamp_col)

    protected_cols = _protected_columns(working, ohlcv_map, price_context)
    column_transforms = state.get("column_transforms") or []
    working = apply_transforms(
        working, column_transforms, timestamp_col, protected_cols=protected_cols
    )

    features = state.get("features") or []
    if features:
        working, err, added = apply_features(working, features, ohlcv_map)
        meta["features_added"] = added
        if err:
            return None, None, err

    if include_label:
        label_cfg = state.get("label")
        if label_cfg:
            ctx = price_context or {}
            if ohlcv_map:
                ctx = {**ctx, "ohlcv_map": ohlcv_map}
            working, err = apply_label(working, label_cfg, ctx)
            if err:
                return None, None, err

    if include_split:
        split_cfg = state.get("split") or {"method": "temporal", "params": {"train_ratio": 0.8}}
        method = split_cfg.get("method", "temporal")
        params = split_cfg.get("params") or {}

        # Embargo = label horizon: purge boundary rows whose forward-looking
        # labels would otherwise leak future (test) information into training.
        embargo = _label_horizon(state.get("label")) if include_label else 0
        meta["embargo"] = embargo

        if method == "walk_forward":
            folds = walk_forward_split(
                working,
                n_splits=int(params.get("n_splits", 5)),
                gap=max(int(params.get("gap", 0)), embargo),
            )
            train_df, test_df = folds[-1]
            meta["split_fold"] = len(folds)
        else:
            train_df, test_df = temporal_split(
                working, float(params.get("train_ratio", 0.8)), embargo=embargo
            )

        meta["train_df"] = train_df
        meta["test_df"] = test_df

    return working, meta, None


def df_to_preview_records(df: pd.DataFrame, limit: int = 20) -> list[dict]:
    preview = df.head(limit).copy()
    for col in preview.columns:
        if pd.api.types.is_datetime64_any_dtype(preview[col]):
            preview[col] = preview[col].astype(str)
    return preview.replace({np.nan: None}).to_dict(orient="records")
