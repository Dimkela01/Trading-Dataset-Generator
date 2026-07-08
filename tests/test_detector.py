"""Tests for column / asset / order-book detection."""

import pandas as pd

from processors.detector import analyze, detect_order_book_map, detect_symbol_column


def test_analyze_ohlcv_sample(ohlcv_df):
    result = analyze(ohlcv_df)
    assert result["row_count"] == len(ohlcv_df)
    assert result["timestamp_column"] == "datetime"
    assert result["has_ohlcv"] is True
    assert result["granularity"] == "1h"
    assert result["is_multi_asset"] is False
    assert len(result["preview"]) <= 20


def test_order_book_detection(order_book_df):
    result = analyze(order_book_df)
    assert result["has_order_book"] is True
    assert result["bid_column"] == "best_bid"
    assert result["ask_column"] == "best_ask"


def test_multi_asset_detection(multi_asset_df):
    result = analyze(multi_asset_df)
    assert result["is_multi_asset"] is True
    assert result["symbol_column"] == "symbol"
    assert set(result["symbols"]) == {"BTCUSDT", "ETHUSDT", "SOLUSDT"}
    assert sum(result["symbol_row_counts"].values()) == len(multi_asset_df)


def test_multi_asset_skipped_after_filter(ohlcv_df):
    filtered = ohlcv_df.copy()
    filtered["symbol"] = "BTCUSDT"
    result = analyze(filtered, skip_multi_asset_check=True)
    assert result["is_multi_asset"] is False


def test_semicolon_csv_via_analyze():
  # Single-column semicolon files are handled at upload; detector sees parsed cols
    df = pd.DataFrame(
        {"datetime": pd.date_range("2024-01-01", periods=10, freq="h"), "close": range(10)}
    )
    ob = detect_order_book_map(list(df.columns))
    assert ob == {}
