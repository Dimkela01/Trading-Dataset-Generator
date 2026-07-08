"""Tests for technical feature engineering and error handling."""

import pandas as pd

from processors.features import apply_features


def test_rsi_on_ohlcv(ohlcv_df):
    df, err, added = apply_features(
        ohlcv_df, [{"type": "rsi", "params": {"period": 14}}], {}
    )
    assert err is None
    assert "rsi_14" in df.columns


def test_rsi_rejected_without_price_column():
    df = pd.DataFrame({"x": [1, 2, 3, 4, 5] * 5})
    out, err, _ = apply_features(df, [{"type": "rsi", "params": {"period": 14}}], {})
    assert out is None
    assert "close" in err.lower() or "price" in err.lower()


def test_vwap_rejected_without_volume(ohlcv_df):
    df = ohlcv_df.drop(columns=["volume"])
    out, err, _ = apply_features(df, [{"type": "vwap", "params": {}}], {})
    assert out is None
    assert "volume" in err.lower()


def test_rsi_with_bid_column_fallback(order_book_df):
    df = order_book_df.drop(columns=["open", "high", "low", "close"])
    out, err, _ = apply_features(df, [{"type": "rsi", "params": {"period": 14}}], {})
    assert err is None
    assert "rsi_14" in out.columns


def test_macd_adds_three_columns(ohlcv_df):
    df, err, added = apply_features(
        ohlcv_df,
        [{"type": "macd", "params": {"fast": 12, "slow": 26, "signal": 9}}],
        {},
    )
    assert err is None
    assert all(c in df.columns for c in ("macd", "macd_signal", "macd_hist"))
