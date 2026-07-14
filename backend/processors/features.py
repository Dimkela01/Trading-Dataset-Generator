import pandas as pd
import pandas_ta as ta

# Column-name fragments that mark a numeric column as *not* a price series
# (so bid/ask matching doesn't accidentally grab a volume/count column).
_NON_PRICE_HINTS = ("vol", "count", "level", "num", "qty", "size", "depth")


def _is_price_col(df: pd.DataFrame, col: str) -> bool:
    norm = str(col).lower()
    if any(h in norm for h in _NON_PRICE_HINTS):
        return False
    return pd.api.types.is_numeric_dtype(df[col])


def _find_price_col(df: pd.DataFrame, keyword: str) -> str | None:
    """First numeric price-like column whose name contains `keyword`."""
    for c in df.columns:
        if keyword in str(c).lower() and _is_price_col(df, c):
            return c
    return None


def _resolve_price(df: pd.DataFrame, ohlcv_map: dict) -> tuple[pd.Series | None, str | None]:
    """
    Resolve the price series that indicators (RSI/MACD/BBands/…) run on, and a
    human-readable label describing where it came from. Priority:
      1. an explicit `close` column from the OHLCV detector
      2. an existing mid-price column (e.g. added via the Mid Price feature)
      3. any column named like a close/trade price
      4. the mid price derived on the fly from bid + ask
      5. a single bid price as a last resort
    """
    # 1. explicit close mapping
    if "close" in ohlcv_map and ohlcv_map["close"] in df.columns:
        c = ohlcv_map["close"]
        return df[c], str(c)
    # 2. existing mid column
    for c in df.columns:
        if str(c).lower() in ("mid", "mid_price", "midprice") and _is_price_col(df, c):
            return df[c], str(c)
    # 3. a close/trade price column
    for c in df.columns:
        if "close" in str(c).lower() and _is_price_col(df, c):
            return df[c], str(c)
    # 4. derive mid from bid + ask
    bid = _find_price_col(df, "bid")
    ask = _find_price_col(df, "ask")
    if bid and ask:
        return (df[bid] + df[ask]) / 2, f"mid price = ({bid} + {ask}) / 2"
    # 5. single bid price
    if bid:
        return df[bid], bid
    return None, None


def _get_volume_col(df: pd.DataFrame, ohlcv_map: dict) -> str | None:
    if "volume" in ohlcv_map and ohlcv_map["volume"] in df.columns:
        return ohlcv_map["volume"]
    for c in df.columns:
        if "vol" in str(c).lower():
            return c
    return None


def apply_features(
    df: pd.DataFrame,
    features_list: list[dict],
    ohlcv_map: dict | None = None,
) -> tuple[pd.DataFrame | None, str | None, list[dict]]:
    ohlcv_map = ohlcv_map or {}
    result = df.copy()
    added_features: list[dict] = []

    high_col = ohlcv_map.get("high")
    low_col = ohlcv_map.get("low")
    vol_col = _get_volume_col(result, ohlcv_map)

    for feat in features_list:
        ftype = feat.get("type")
        params = feat.get("params") or {}

        try:
            if ftype == "mid":
                bid = params.get("col_bid")
                ask = params.get("col_ask")
                if bid not in result.columns or ask not in result.columns:
                    return None, "Mid Price needs a valid bid and ask column", added_features
                result["mid"] = (result[bid] + result[ask]) / 2
                added_features.append(
                    {
                        "type": "mid",
                        "params": params,
                        "columns": ["mid"],
                        "source": f"({bid} + {ask}) / 2",
                    }
                )

            elif ftype == "rsi":
                price, src = _resolve_price(result, ohlcv_map)
                if price is None:
                    return None, "RSI requires a close/price column", added_features
                period = int(params.get("period", 14))
                col_name = f"rsi_{period}"
                result[col_name] = ta.rsi(price, length=period)
                added_features.append(
                    {"type": "rsi", "params": params, "columns": [col_name], "source": src}
                )

            elif ftype == "macd":
                price, src = _resolve_price(result, ohlcv_map)
                if price is None:
                    return None, "MACD requires a close/price column", added_features
                fast = int(params.get("fast", 12))
                slow = int(params.get("slow", 26))
                signal = int(params.get("signal", 9))
                macd = ta.macd(price, fast=fast, slow=slow, signal=signal)
                if macd is None:
                    return None, "MACD could not be computed", added_features
                result["macd"] = macd.iloc[:, 0]
                result["macd_signal"] = macd.iloc[:, 1]
                result["macd_hist"] = macd.iloc[:, 2]
                added_features.append(
                    {
                        "type": "macd",
                        "params": params,
                        "columns": ["macd", "macd_signal", "macd_hist"],
                        "source": src,
                    }
                )

            elif ftype == "bbands":
                price, src = _resolve_price(result, ohlcv_map)
                if price is None:
                    return None, "Bollinger Bands require a close/price column", added_features
                period = int(params.get("period", 20))
                std = float(params.get("std", 2))
                bb = ta.bbands(price, length=period, std=std)
                if bb is None:
                    return None, "Bollinger Bands could not be computed", added_features
                result["bb_upper"] = bb.iloc[:, 0]
                result["bb_mid"] = bb.iloc[:, 1]
                result["bb_lower"] = bb.iloc[:, 2]
                result["bb_width"] = (result["bb_upper"] - result["bb_lower"]) / result["bb_mid"]
                added_features.append(
                    {
                        "type": "bbands",
                        "params": params,
                        "columns": ["bb_upper", "bb_mid", "bb_lower", "bb_width"],
                        "source": src,
                    }
                )

            elif ftype == "atr":
                price, src = _resolve_price(result, ohlcv_map)
                if price is None:
                    return None, "ATR requires OHLC columns", added_features
                period = int(params.get("period", 14))
                col_name = f"atr_{period}"
                if high_col and low_col and high_col in result.columns and low_col in result.columns:
                    result[col_name] = ta.atr(
                        result[high_col], result[low_col], price, length=period
                    )
                    src = f"high={high_col}, low={low_col}, close={src}"
                else:
                    result[col_name] = ta.atr(price, price, price, length=period)
                    src = f"{src} (no high/low — close-only)"
                added_features.append(
                    {"type": "atr", "params": params, "columns": [col_name], "source": src}
                )

            elif ftype == "vwap":
                if vol_col is None:
                    return None, "VWAP requires a volume column", added_features
                price, src = _resolve_price(result, ohlcv_map)
                if price is None:
                    return None, "VWAP requires a close/price column", added_features
                if high_col and low_col and high_col in result.columns and low_col in result.columns:
                    result["vwap"] = ta.vwap(
                        result[high_col], result[low_col], price, result[vol_col]
                    )
                    src = f"high={high_col}, low={low_col}, close={src}, volume={vol_col}"
                else:
                    result["vwap"] = ta.vwap(price, price, price, result[vol_col])
                    src = f"price={src}, volume={vol_col}"
                added_features.append(
                    {"type": "vwap", "params": params, "columns": ["vwap"], "source": src}
                )

            elif ftype == "lag":
                col = params.get("column")
                periods = int(params.get("periods", 1))
                if col not in result.columns:
                    return None, f"Lag column '{col}' not found in dataset", added_features
                col_name = f"{col}_lag_{periods}"
                result[col_name] = result[col].shift(periods)
                added_features.append(
                    {"type": "lag", "params": params, "columns": [col_name], "source": col}
                )

            elif ftype == "ratio":
                col_a = params.get("col_a")
                col_b = params.get("col_b")
                if col_a not in result.columns or col_b not in result.columns:
                    return None, f"Ratio columns '{col_a}' and '{col_b}' must exist", added_features
                col_name = f"{col_a}_div_{col_b}"
                result[col_name] = result[col_a] / result[col_b].replace(0, float("nan"))
                added_features.append(
                    {
                        "type": "ratio",
                        "params": params,
                        "columns": [col_name],
                        "source": f"{col_a} / {col_b}",
                    }
                )

            elif ftype == "diff":
                col_a = params.get("col_a")
                col_b = params.get("col_b")
                if col_a not in result.columns or col_b not in result.columns:
                    return None, f"Diff columns '{col_a}' and '{col_b}' must exist", added_features
                col_name = f"{col_a}_minus_{col_b}"
                result[col_name] = result[col_a] - result[col_b]
                added_features.append(
                    {
                        "type": "diff",
                        "params": params,
                        "columns": [col_name],
                        "source": f"{col_a} - {col_b}",
                    }
                )

            else:
                return None, f"Unknown feature type: {ftype}", added_features

        except Exception as e:
            return None, f"Feature '{ftype}' failed: {str(e)}", added_features

    return result, None, added_features
