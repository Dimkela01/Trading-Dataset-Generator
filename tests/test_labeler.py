"""Tests for label generation strategies and framings."""

import numpy as np
import pandas as pd

from processors.labeler import apply_label


def _ctx(df, ohlcv_map=None, bid="best_bid", ask="best_ask"):
    ctx = {"ohlcv_map": ohlcv_map or {"close": "close"}}
    if bid in df.columns:
        ctx["bid_column"] = bid
    if ask in df.columns:
        ctx["ask_column"] = ask
    return ctx


def test_forward_return_regression(ohlcv_df):
    cfg = {"method": "forward_return", "params": {"periods": 5, "mode": "regression"}}
    out, err = apply_label(ohlcv_df, cfg, _ctx(ohlcv_df))
    assert err is None
    assert "label" in out.columns
    assert out["label"].notna().sum() > 0
    # Last rows may be NaN before dropna
    assert np.isfinite(out["label"].iloc[10])


def test_forward_return_mid_classification(ohlcv_df):
    cfg = {
        "method": "forward_return",
        "params": {
            "periods": 5,
            "mode": "classification",
            "framing": "mid_price_direction",
            "up_threshold": 0.001,
            "down_threshold": -0.001,
        },
    }
    out, err = apply_label(ohlcv_df, cfg, _ctx(ohlcv_df))
    assert err is None
    assert set(out["label"].dropna().unique()).issubset({-1.0, 0.0, 1.0})


def test_execution_aware_both_columns(order_book_df):
    cfg = {
        "method": "forward_return",
        "params": {
            "periods": 5,
            "mode": "classification",
            "framing": "execution_aware",
            "direction": "both",
            "min_profit_threshold": 0.0001,
        },
    }
    out, err = apply_label(order_book_df, cfg, _ctx(order_book_df))
    assert err is None
    assert "label_long" in out.columns
    assert "label_short" in out.columns


def test_execution_aware_rejected_without_order_book(ohlcv_df):
    cfg = {
        "method": "forward_return",
        "params": {
            "periods": 5,
            "mode": "classification",
            "framing": "execution_aware",
            "direction": "long",
        },
    }
    out, err = apply_label(ohlcv_df, cfg, _ctx(ohlcv_df, bid=None, ask=None))
    assert out is None
    assert "bid" in err.lower() or "ask" in err.lower()


def test_triple_barrier_simple(ohlcv_df):
    cfg = {
        "method": "triple_barrier",
        "params": {"tp": 0.02, "sl": 0.02, "max_periods": 5, "barrier_mode": "simple"},
    }
    out, err = apply_label(ohlcv_df, cfg, _ctx(ohlcv_df))
    assert err is None
    assert set(out["label"].unique()).issubset({-1.0, 0.0, 1.0})


def test_triple_barrier_realistic(order_book_df):
    cfg = {
        "method": "triple_barrier",
        "params": {"tp": 0.01, "sl": 0.01, "max_periods": 5, "barrier_mode": "realistic"},
    }
    out, err = apply_label(order_book_df, cfg, _ctx(order_book_df))
    assert err is None
    assert "label" in out.columns


def test_custom_expression(ohlcv_df):
    cfg = {
        "method": "custom",
        "params": {"expression": "close > close.shift(1)"},
    }
    out, err = apply_label(ohlcv_df, cfg, _ctx(ohlcv_df))
    assert err is None
    assert out["label"].isin([0.0, 1.0]).all()
