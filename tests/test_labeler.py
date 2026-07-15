"""Tests for label generation strategies and framings."""

import numpy as np
import pandas as pd
import pytest

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


def test_custom_expression_binds_real_column_not_derived(ohlcv_df):
    """`close` must mean the close column, even when `close_log_return` exists.

    Binding roles by substring picked the *last* matching column, so a derived
    column silently hijacked the name and produced a plausible-looking but
    completely different label.
    """
    df = ohlcv_df.copy()
    df["close_log_return"] = np.log(df["close"] / df["close"].shift(1))

    expr = {"method": "custom", "params": {"expression": "close > close.shift(1)"}}
    with_derived, err = apply_label(df, expr, _ctx(df))
    assert err is None
    without_derived, err = apply_label(ohlcv_df, expr, _ctx(ohlcv_df))
    assert err is None

    expected = (ohlcv_df["close"] > ohlcv_df["close"].shift(1)).astype(float)
    assert with_derived["label"].tolist() == expected.dropna().tolist()
    assert with_derived["label"].tolist() == without_derived["label"].tolist()


def test_custom_expression_role_alias_resolves_via_ohlcv_map(ohlcv_df):
    """A file that doesn't name its price column `close` can still say `close`."""
    df = ohlcv_df.rename(columns={"close": "px_last"})
    cfg = {"method": "custom", "params": {"expression": "close > close.shift(1)"}}
    out, err = apply_label(df, cfg, {"ohlcv_map": {"close": "px_last"}})
    assert err is None
    expected = (df["px_last"] > df["px_last"].shift(1)).astype(float)
    assert out["label"].tolist() == expected.dropna().tolist()


def test_custom_expression_rejects_side_effecting_call(ohlcv_df, tmp_path):
    """`pd.eval` executes arbitrary methods — `to_csv` really did write a file."""
    target = tmp_path / "pwned.csv"
    cfg = {
        "method": "custom",
        "params": {"expression": f"close.to_csv({str(target)!r})"},
    }
    out, err = apply_label(ohlcv_df, cfg, _ctx(ohlcv_df))
    assert out is None
    assert "to_csv" in err
    assert not target.exists()


@pytest.mark.parametrize(
    "expression",
    [
        "close.__class__",
        "close.shift.__globals__",
        "close.apply(print)",
        "__import__('os').system('echo hi')",
        "[c for c in close]",
        "close[0]",
        "open('x', 'w')",
    ],
)
def test_custom_expression_rejects_escapes(ohlcv_df, expression):
    cfg = {"method": "custom", "params": {"expression": expression}}
    out, err = apply_label(ohlcv_df, cfg, _ctx(ohlcv_df))
    assert out is None, f"{expression!r} should have been rejected"
    assert err


def test_custom_expression_unknown_name_is_explained(ohlcv_df):
    cfg = {"method": "custom", "params": {"expression": "nonexistent > 1"}}
    out, err = apply_label(ohlcv_df, cfg, _ctx(ohlcv_df))
    assert out is None
    assert "nonexistent" in err
    assert "close" in err  # lists what *is* available


def test_custom_expression_allows_arithmetic_and_funcs(ohlcv_df):
    cfg = {
        "method": "custom",
        "params": {"expression": "(log(close / close.shift(1)) > 0) & (volume > 0)"},
    }
    out, err = apply_label(ohlcv_df, cfg, _ctx(ohlcv_df))
    assert err is None
    assert out["label"].isin([0.0, 1.0]).all()
