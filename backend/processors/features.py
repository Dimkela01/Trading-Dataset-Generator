import pandas as pd
import pandas_ta as ta


def _get_close_col(df: pd.DataFrame, ohlcv_map: dict) -> str | None:
    if "close" in ohlcv_map and ohlcv_map["close"] in df.columns:
        return ohlcv_map["close"]
    for c in df.columns:
        norm = str(c).lower()
        if "close" in norm:
            return c
    for c in df.columns:
        norm = str(c).lower()
        if "bid" in norm and pd.api.types.is_numeric_dtype(df[c]):
            return c
    return None


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

    close_col = _get_close_col(result, ohlcv_map)
    high_col = ohlcv_map.get("high")
    low_col = ohlcv_map.get("low")
    vol_col = _get_volume_col(result, ohlcv_map)

    for feat in features_list:
        ftype = feat.get("type")
        params = feat.get("params") or {}

        try:
            if ftype == "rsi":
                if close_col is None:
                    return None, "RSI requires a close/price column", added_features
                period = int(params.get("period", 14))
                col_name = f"rsi_{period}"
                result[col_name] = ta.rsi(result[close_col], length=period)
                added_features.append({"type": "rsi", "params": params, "columns": [col_name]})

            elif ftype == "macd":
                if close_col is None:
                    return None, "MACD requires a close/price column", added_features
                fast = int(params.get("fast", 12))
                slow = int(params.get("slow", 26))
                signal = int(params.get("signal", 9))
                macd = ta.macd(result[close_col], fast=fast, slow=slow, signal=signal)
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
                    }
                )

            elif ftype == "bbands":
                if close_col is None:
                    return None, "Bollinger Bands require a close/price column", added_features
                period = int(params.get("period", 20))
                std = float(params.get("std", 2))
                bb = ta.bbands(result[close_col], length=period, std=std)
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
                    }
                )

            elif ftype == "atr":
                if not all(c in result.columns for c in [high_col, low_col, close_col] if c):
                    if close_col is None:
                        return None, "ATR requires OHLC columns", added_features
                period = int(params.get("period", 14))
                col_name = f"atr_{period}"
                if high_col and low_col and close_col:
                    result[col_name] = ta.atr(
                        result[high_col], result[low_col], result[close_col], length=period
                    )
                elif close_col:
                    result[col_name] = ta.atr(
                        result[close_col], result[close_col], result[close_col], length=period
                    )
                else:
                    return None, "ATR requires high, low, and close columns", added_features
                added_features.append({"type": "atr", "params": params, "columns": [col_name]})

            elif ftype == "vwap":
                if vol_col is None:
                    return None, "VWAP requires a volume column", added_features
                if close_col is None:
                    return None, "VWAP requires a close/price column", added_features
                if high_col and low_col:
                    result["vwap"] = ta.vwap(
                        result[high_col], result[low_col], result[close_col], result[vol_col]
                    )
                else:
                    result["vwap"] = ta.vwap(
                        result[close_col], result[close_col], result[close_col], result[vol_col]
                    )
                added_features.append({"type": "vwap", "params": params, "columns": ["vwap"]})

            elif ftype == "lag":
                col = params.get("column")
                periods = int(params.get("periods", 1))
                if col not in result.columns:
                    return None, f"Lag column '{col}' not found in dataset", added_features
                col_name = f"{col}_lag_{periods}"
                result[col_name] = result[col].shift(periods)
                added_features.append({"type": "lag", "params": params, "columns": [col_name]})

            elif ftype == "ratio":
                col_a = params.get("col_a")
                col_b = params.get("col_b")
                if col_a not in result.columns or col_b not in result.columns:
                    return None, f"Ratio columns '{col_a}' and '{col_b}' must exist", added_features
                col_name = f"{col_a}_div_{col_b}"
                result[col_name] = result[col_a] / result[col_b].replace(0, float("nan"))
                added_features.append({"type": "ratio", "params": params, "columns": [col_name]})

            elif ftype == "diff":
                col_a = params.get("col_a")
                col_b = params.get("col_b")
                if col_a not in result.columns or col_b not in result.columns:
                    return None, f"Diff columns '{col_a}' and '{col_b}' must exist", added_features
                col_name = f"{col_a}_minus_{col_b}"
                result[col_name] = result[col_a] - result[col_b]
                added_features.append({"type": "diff", "params": params, "columns": [col_name]})

            else:
                return None, f"Unknown feature type: {ftype}", added_features

        except Exception as e:
            return None, f"Feature '{ftype}' failed: {str(e)}", added_features

    return result, None, added_features
