from typing import Any

import numpy as np
import pandas as pd

from processors.transformer import apply_transforms
from processors.features import apply_features
from processors.labeler import apply_label, predicted_label_columns
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


def _drop_incomplete_rows(
    df: pd.DataFrame, timestamp_col: str | None
) -> tuple[pd.DataFrame, int]:
    """Drop rows the model can't learn from before splitting.

    Two sources of NaN contaminate a freshly engineered frame: leading *warmup*
    rows where rolling windows / returns haven't filled yet, and trailing rows
    where a forward-looking label peeked past the end of the data. Both leave
    NaNs in the numeric feature/label matrix. We drop any row with a NaN in a
    numeric column (the timestamp is metadata, not a feature, so it's exempt),
    yielding a train/test set with no gaps. Returns the cleaned frame and the
    number of rows removed."""
    check_cols = [
        c
        for c in df.columns
        if c != timestamp_col and pd.api.types.is_numeric_dtype(df[c])
    ]
    if not check_cols:
        return df, 0
    before = len(df)
    cleaned = df.dropna(subset=check_cols).reset_index(drop=True)
    return cleaned, before - len(cleaned)


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
    soft_label: bool = False,
) -> tuple[pd.DataFrame | None, dict[str, Any] | None, str | None]:
    """Run the configured stages in dependency order.

    Order is: sort → derive transforms → features → label → retire columns →
    drop incomplete rows → split. Column removal deliberately comes *last* among
    the column stages so features and labels can consume a column the user has
    unticked (see ``transformer.apply_transforms``).

    With `soft_label`, a label failure is reported in ``meta["label_error"]``
    and the frame is returned unlabeled rather than collapsing the whole run —
    the wizard needs to keep showing the column/feature preview while the user
    is still typing a custom expression. Every other stage behaves identically,
    so what the preview shows is what the export writes.
    """
    meta: dict[str, Any] = {"features_added": []}
    ohlcv_map = ohlcv_map or {}

    working = df.copy()
    working = _sort_by_time(working, timestamp_col)

    protected_cols = _protected_columns(working, ohlcv_map, price_context)
    column_transforms = state.get("column_transforms") or []
    working, deferred_drops = apply_transforms(
        working, column_transforms, timestamp_col, protected_cols=protected_cols
    )

    features = state.get("features") or []
    if features:
        working, err, added = apply_features(working, features, ohlcv_map)
        meta["features_added"] = added
        if err:
            return None, None, err

    # What a feature picker or custom expression may legitimately reference:
    # everything derived so far, *including* originals awaiting a deferred drop.
    # This is deliberately not the exported column set.
    meta["available_columns"] = [
        str(c)
        for c in working.columns
        if c != timestamp_col and pd.api.types.is_numeric_dtype(working[c])
    ]
    meta["rows_after_features"] = len(working)

    meta["label_error"] = None
    meta["label_collisions"] = []
    generated_label_cols: set[str] = set()
    label_cfg = state.get("label") if include_label else None
    if label_cfg and label_cfg.get("method"):
        generated_label_cols = set(predicted_label_columns(label_cfg))
        # A generated label would overwrite a same-named user column; the labeler
        # preserves theirs as "<name>_source". Report which so the UI can say so.
        meta["label_collisions"] = [
            c for c in predicted_label_columns(label_cfg) if c in working.columns
        ]
        ctx = price_context or {}
        if ohlcv_map:
            ctx = {**ctx, "ohlcv_map": ohlcv_map}
        labeled, err = apply_label(working, label_cfg, ctx)
        if err:
            if not soft_label:
                return None, None, err
            meta["label_error"] = err
        else:
            working = labeled

    # Retire the unticked/superseded columns now that features and labels have
    # had their chance to read them. Generated label columns are never dropped:
    # a user column named "label" that was unticked has already been renamed to
    # "label_source" by the labeler, so dropping "label" here would delete the
    # target we just created.
    drops = [
        c for c in working.columns
        if c in deferred_drops and c not in generated_label_cols
    ]
    if drops:
        working = working.drop(columns=drops)
    meta["columns_dropped"] = drops

    if include_split:
        split_cfg = state.get("split") or {"method": "temporal", "params": {"train_ratio": 0.8}}
        method = split_cfg.get("method", "temporal")
        params = split_cfg.get("params") or {}

        # Drop warmup / forward-label NaN rows so the exported train/test sets
        # contain a fully-populated feature matrix (see _drop_incomplete_rows).
        rows_before = len(working)
        working, dropped = _drop_incomplete_rows(working, timestamp_col)
        meta["rows_dropped_incomplete"] = dropped
        meta["rows_before_clean"] = rows_before

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


def warmup_offset(df: pd.DataFrame, timestamp_col: str | None) -> int:
    """Row position where every numeric column is first populated.

    Rolling/return features leave the leading rows NaN, so ``df.head()`` would
    show the user a wall of blanks right after they add the feature they're
    tuning. Starting the preview here lets them see real computed values. The
    timestamp is exempt (it's never a feature). Returns 0 when nothing is fully
    populated (e.g. an all-NaN column) so the caller falls back to the head."""
    num_cols = [
        c
        for c in df.columns
        if c != timestamp_col and pd.api.types.is_numeric_dtype(df[c])
    ]
    if not num_cols:
        return 0
    all_valid = df[num_cols].notna().all(axis=1).to_numpy()
    if not all_valid.any():
        return 0
    return int(all_valid.argmax())


def df_to_preview_records(df: pd.DataFrame, limit: int = 20) -> list[dict]:
    preview = df.head(limit).copy()
    for col in preview.columns:
        if pd.api.types.is_datetime64_any_dtype(preview[col]):
            preview[col] = preview[col].astype(str)
    return preview.replace({np.nan: None}).to_dict(orient="records")
