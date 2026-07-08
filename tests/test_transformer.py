"""Tests for column transformations."""

import pandas as pd

from processors.transformer import apply_transforms


def test_log_return_creates_new_column(ohlcv_df):
    transforms = [{"column": "close", "transform": "log_return", "params": {}}]
    out = apply_transforms(ohlcv_df, transforms, timestamp_col="datetime")
    assert "close_log_return" in out.columns
    assert "close" not in out.columns


def test_drop_column(ohlcv_df):
    transforms = [{"column": "volume", "transform": "drop", "params": {}}]
    out = apply_transforms(ohlcv_df, transforms, timestamp_col="datetime")
    assert "volume" not in out.columns
    assert "datetime" in out.columns


def test_z_score_requires_window(ohlcv_df):
    transforms = [{"column": "close", "transform": "z_score", "params": {"window": 10}}]
    out = apply_transforms(ohlcv_df, transforms, timestamp_col="datetime")
    assert "close_z_score_10" in out.columns
