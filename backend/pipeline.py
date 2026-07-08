from typing import Any

import numpy as np
import pandas as pd

from processors.transformer import apply_transforms
from processors.features import apply_features
from processors.labeler import apply_label
from processors.splitter import temporal_split, walk_forward_split


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
    column_transforms = state.get("column_transforms") or []
    working = apply_transforms(working, column_transforms, timestamp_col)

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

        if method == "walk_forward":
            folds = walk_forward_split(
                working,
                n_splits=int(params.get("n_splits", 5)),
                gap=int(params.get("gap", 0)),
            )
            train_df, test_df = folds[-1]
            meta["split_fold"] = len(folds)
        else:
            train_df, test_df = temporal_split(working, float(params.get("train_ratio", 0.8)))

        meta["train_df"] = train_df
        meta["test_df"] = test_df

    return working, meta, None


def df_to_preview_records(df: pd.DataFrame, limit: int = 20) -> list[dict]:
    preview = df.head(limit).copy()
    for col in preview.columns:
        if pd.api.types.is_datetime64_any_dtype(preview[col]):
            preview[col] = preview[col].astype(str)
    return preview.replace({np.nan: None}).to_dict(orient="records")
