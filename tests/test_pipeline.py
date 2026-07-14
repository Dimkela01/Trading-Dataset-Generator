"""End-to-end pipeline orchestration tests."""

import io
import zipfile

import pyarrow.parquet as pq

from pipeline import run_pipeline


def test_full_pipeline_temporal_export_shape(ohlcv_df):
    state = {
        "column_transforms": [
            {"column": "close", "transform": "log_return", "params": {}},
        ],
        "features": [{"type": "rsi", "params": {"period": 14}}],
        "label": {
            "method": "forward_return",
            "params": {"periods": 5, "mode": "regression"},
        },
        "split": {"method": "temporal", "params": {"train_ratio": 0.8}},
    }
    ohlcv_map = {"close": "close", "open": "open", "high": "high", "low": "low", "volume": "volume"}
    result, meta, err = run_pipeline(
        ohlcv_df,
        state,
        timestamp_col="datetime",
        ohlcv_map=ohlcv_map,
        include_label=True,
        include_split=True,
    )
    assert err is None
    assert "label" in result.columns
    assert "rsi_14" in result.columns
    # `close` is a protected OHLCV column: transforming it keeps the original
    # (so RSI can still resolve a price) and adds the derived column.
    assert "close" in result.columns
    assert "close_log_return" in result.columns
    train, test = meta["train_df"], meta["test_df"]
    # Forward-return horizon of 5 embargoes 5 rows at the split boundary to
    # prevent train labels leaking into the test window.
    assert meta["embargo"] == 5
    assert len(train) + len(test) == len(result) - meta["embargo"]
    assert len(train) > len(test)


def test_pipeline_sorts_unsorted_input(ohlcv_df):
    """Rows arriving out of chronological order must be sorted before any
    shift-based op, otherwise returns/labels/splits are silently wrong."""
    shuffled = ohlcv_df.sample(frac=1.0, random_state=0).reset_index(drop=True)
    state = {
        "column_transforms": [],
        "features": [],
        "label": {"method": "forward_return", "params": {"periods": 3, "mode": "regression"}},
        "split": {"method": "temporal", "params": {"train_ratio": 0.8}},
    }
    result, meta, err = run_pipeline(
        shuffled,
        state,
        timestamp_col="datetime",
        include_label=True,
        include_split=True,
    )
    assert err is None
    ts = result["datetime"].tolist()
    assert ts == sorted(ts)  # output is chronological regardless of input order


def test_pipeline_feature_error_surfaces(ohlcv_df):
    state = {
        "column_transforms": [],
        "features": [{"type": "vwap", "params": {}}],
    }
    df = ohlcv_df.drop(columns=["volume"])
    result, meta, err = run_pipeline(
        df, state, timestamp_col="datetime", include_label=False, include_split=False
    )
    assert result is None
    assert "volume" in err.lower()


def test_walk_forward_uses_last_fold(ohlcv_df):
    state = {
        "column_transforms": [],
        "features": [],
        "label": None,
        "split": {"method": "walk_forward", "params": {"n_splits": 3, "gap": 0}},
    }
    result, meta, err = run_pipeline(
        ohlcv_df,
        state,
        timestamp_col="datetime",
        include_label=False,
        include_split=True,
    )
    assert err is None
    assert meta.get("split_fold", 0) >= 1
    assert len(meta["train_df"]) > len(meta["test_df"])
