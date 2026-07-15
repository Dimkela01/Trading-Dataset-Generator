import re
from typing import Any

import numpy as np
import pandas as pd

TIMESTAMP_KEYWORDS = ("time", "date", "timestamp", "dt", "index")
OHLCV_TARGETS = {
    "open": ("open", "o"),
    "high": ("high", "h"),
    "low": ("low", "l"),
    "close": ("close", "c", "adj_close", "adj close"),
    "volume": ("volume", "vol", "v"),
}

ORDER_BOOK_TARGETS = {
    "bid": ("best_bid", "bid_price", "bid", "bestbid"),
    "ask": ("best_ask", "ask_price", "ask", "bestask"),
}

SYMBOL_KEYWORDS = (
    "symbol", "ticker", "asset", "instrument", "pair", "market", "code", "name",
)

STANDARD_INTERVALS = [
    ("tick", pd.Timedelta(0)),
    ("1min", pd.Timedelta(minutes=1)),
    ("5min", pd.Timedelta(minutes=5)),
    ("15min", pd.Timedelta(minutes=15)),
    ("30min", pd.Timedelta(minutes=30)),
    ("1h", pd.Timedelta(hours=1)),
    ("4h", pd.Timedelta(hours=4)),
    ("1d", pd.Timedelta(days=1)),
]


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _fuzzy_match(name: str, targets: tuple[str, ...]) -> bool:
    norm = _normalize_name(name)
    for t in targets:
        if len(t) <= 1:
            # Single-letter aliases (o/h/l/c/v) must match the *whole* name, not
            # a substring — otherwise "c" grabs bid_levels_count, "v" grabs any
            # column with a v, and a book-only file mis-reports full OHLCV.
            if norm == t:
                return True
        elif t in norm or norm in t:
            return True
    return False


def detect_timestamp_column(df: pd.DataFrame) -> str | None:
    candidates = []
    for col in df.columns:
        norm = _normalize_name(str(col))
        if any(kw in norm for kw in TIMESTAMP_KEYWORDS):
            candidates.append(col)
    if not candidates:
        candidates = list(df.columns)

    for col in candidates:
        try:
            parsed = pd.to_datetime(df[col], errors="coerce")
            if parsed.notna().sum() > len(df) * 0.5:
                return col
        except Exception:
            continue
    return None


def detect_order_book_map(columns: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    used = set()
    for role, targets in ORDER_BOOK_TARGETS.items():
        for col in columns:
            if col in used:
                continue
            if _fuzzy_match(str(col), targets):
                mapping[role] = col
                used.add(col)
                break
    return mapping


def detect_symbol_column(
    df: pd.DataFrame,
    timestamp_col: str | None,
) -> tuple[str | None, list[str], dict[str, int]]:
    """Find a column that stacks multiple instruments into one file.

    Gated on the column *name* matching a symbol keyword — a strong, low
    false-positive signal — so we can afford to relax every other threshold:

    - numeric symbol codes are accepted (an integer ``symbol_id`` is common);
    - up to 1000 distinct instruments (stacked S&P 500 / crypto universes);
    - no minimum row count, so small multi-asset files are still caught.

    The only structural guard is that the column must partition rows into
    *repeated* blocks (``n_unique <= n/2``): each symbol spans many bars. That
    rejects near-unique id or continuous price columns that happen to be named
    like a symbol.
    """
    n = len(df)
    if n < 2:
        return None, [], {}

    for col in df.columns:
        if timestamp_col and col == timestamp_col:
            continue

        norm = _normalize_name(str(col))
        if not any(kw in norm for kw in SYMBOL_KEYWORDS):
            continue

        series = df[col]
        n_unique = series.nunique(dropna=True)
        if n_unique < 2 or n_unique > 1000:
            continue
        if n_unique > n / 2:
            continue

        counts = series.value_counts().to_dict()
        symbols = [str(k) for k in counts.keys()]
        symbol_counts = {str(k): int(v) for k, v in counts.items()}
        return str(col), symbols, symbol_counts

    return None, [], {}


def detect_ohlcv_map(columns: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    used = set()
    for role, targets in OHLCV_TARGETS.items():
        for col in columns:
            if col in used:
                continue
            if _fuzzy_match(str(col), targets):
                mapping[role] = col
                used.add(col)
                break
    return mapping


def detect_granularity(ts_series: pd.Series) -> str:
    ts = pd.to_datetime(ts_series, errors="coerce").dropna().sort_values()
    if len(ts) < 2:
        return "unknown"
    diffs = ts.diff().dropna()
    if diffs.empty:
        return "unknown"
    median_delta = diffs.median()
    if median_delta <= pd.Timedelta(seconds=1):
        return "tick"

    best_label = "1d"
    best_diff = float("inf")
    for label, td in STANDARD_INTERVALS[1:]:
        diff = abs((median_delta - td).total_seconds())
        if diff < best_diff:
            best_diff = diff
            best_label = label
    return best_label


def count_gaps(ts_series: pd.Series, median_delta: pd.Timedelta | None = None) -> int:
    ts = pd.to_datetime(ts_series, errors="coerce").dropna().sort_values()
    if len(ts) < 2:
        return 0
    diffs = ts.diff().dropna()
    if median_delta is None:
        median_delta = diffs.median()
    if pd.isna(median_delta) or median_delta <= pd.Timedelta(0):
        return 0
    threshold = median_delta * 1.5
    return int((diffs > threshold).sum())


def infer_column_type(name: str, series: pd.Series, timestamp_col: str | None) -> str:
    if timestamp_col and name == timestamp_col:
        return "timestamp"
    norm = _normalize_name(str(name))
    if any(kw in norm for kw in ("time", "date", "timestamp", "dt")):
        return "timestamp"
    if _fuzzy_match(name, OHLCV_TARGETS["volume"]):
        return "volume"
    if _fuzzy_match(name, OHLCV_TARGETS["open"] + OHLCV_TARGETS["high"] + OHLCV_TARGETS["low"] + OHLCV_TARGETS["close"]):
        return "price"
    if pd.api.types.is_numeric_dtype(series):
        return "price"
    return "unknown"


def analyze(df: pd.DataFrame, *, skip_multi_asset_check: bool = False) -> dict[str, Any]:
    df = df.copy()
    timestamp_col = detect_timestamp_column(df)
    ohlcv_map = detect_ohlcv_map(list(df.columns.astype(str)))
    order_book_map = detect_order_book_map(list(df.columns.astype(str)))
    has_ohlcv = all(k in ohlcv_map for k in ("open", "high", "low", "close", "volume"))
    has_order_book = "bid" in order_book_map and "ask" in order_book_map
    bid_column = order_book_map.get("bid")
    ask_column = order_book_map.get("ask")

    symbol_column, symbols, symbol_row_counts = detect_symbol_column(df, timestamp_col)
    is_multi_asset = bool(symbol_column and symbols and not skip_multi_asset_check)

    granularity = "unknown"
    gaps = 0
    if timestamp_col:
        ts = pd.to_datetime(df[timestamp_col], errors="coerce")
        granularity = detect_granularity(ts)
        diffs = ts.sort_values().diff().dropna()
        median_delta = diffs.median() if not diffs.empty else None
        gaps = count_gaps(ts, median_delta)

    duplicate_rows = int(df.duplicated().sum())

    columns_info = []
    for col in df.columns:
        series = df[col]
        missing_count = int(series.isna().sum())
        missing_pct = round(missing_count / len(df) * 100, 2) if len(df) else 0.0
        columns_info.append(
            {
                "name": str(col),
                "detected_type": infer_column_type(str(col), series, timestamp_col),
                "dtype": str(series.dtype),
                "missing_count": missing_count,
                "missing_pct": missing_pct,
            }
        )

    preview_df = df.head(20).copy()
    for col in preview_df.columns:
        if pd.api.types.is_datetime64_any_dtype(preview_df[col]):
            preview_df[col] = preview_df[col].astype(str)

    preview = preview_df.replace({np.nan: None}).to_dict(orient="records")

    return {
        "columns": columns_info,
        "granularity": granularity,
        "row_count": len(df),
        "timestamp_column": timestamp_col,
        "has_ohlcv": has_ohlcv,
        "has_order_book": has_order_book,
        "bid_column": bid_column,
        "ask_column": ask_column,
        "ohlcv_map": ohlcv_map,
        "gaps_detected": gaps,
        "duplicate_rows": duplicate_rows,
        "preview": preview,
        "is_multi_asset": is_multi_asset,
        "symbol_column": symbol_column,
        "symbols": symbols if is_multi_asset else [],
        "symbol_row_counts": symbol_row_counts if is_multi_asset else {},
    }
