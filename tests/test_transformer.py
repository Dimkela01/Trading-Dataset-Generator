"""Tests for column transformations."""

import pandas as pd

from processors.transformer import apply_transforms


def test_log_return_creates_new_column(ohlcv_df):
    transforms = [{"column": "close", "transform": "log_return", "params": {}}]
    out, drops = apply_transforms(ohlcv_df, transforms, timestamp_col="datetime")
    assert "close_log_return" in out.columns
    # The superseded original is reported for a later drop, not removed here —
    # features and labels still need to read it (see apply_transforms).
    assert "close" in out.columns
    assert "close" in drops


def test_protected_column_is_not_superseded(ohlcv_df):
    transforms = [{"column": "close", "transform": "log_return", "params": {}}]
    out, drops = apply_transforms(
        ohlcv_df, transforms, timestamp_col="datetime", protected_cols={"close"}
    )
    assert "close_log_return" in out.columns
    assert "close" not in drops


def test_drop_is_deferred_not_immediate(ohlcv_df):
    transforms = [{"column": "volume", "transform": "drop", "params": {}}]
    out, drops = apply_transforms(ohlcv_df, transforms, timestamp_col="datetime")
    assert drops == {"volume"}
    assert "volume" in out.columns  # still available to downstream stages
    assert "datetime" in out.columns


def test_z_score_requires_window(ohlcv_df):
    transforms = [{"column": "close", "transform": "z_score", "params": {"window": 10}}]
    out, _ = apply_transforms(ohlcv_df, transforms, timestamp_col="datetime")
    assert "close_z_score_10" in out.columns
