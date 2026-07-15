import numpy as np
import pandas as pd

LABEL_COLUMNS = ("label", "label_long", "label_short")


def _get_close_col(df: pd.DataFrame, ohlcv_map: dict | None) -> str | None:
    ohlcv_map = ohlcv_map or {}
    if "close" in ohlcv_map and ohlcv_map["close"] in df.columns:
        return ohlcv_map["close"]
    for c in df.columns:
        if "close" in str(c).lower() and pd.api.types.is_numeric_dtype(df[c]):
            return c
    return None


def _resolve_bid_ask(
    df: pd.DataFrame,
    price_context: dict | None,
) -> tuple[str | None, str | None]:
    ctx = price_context or {}
    bid = ctx.get("bid_column")
    ask = ctx.get("ask_column")
    if bid and bid in df.columns:
        pass
    else:
        bid = None
    if ask and ask in df.columns:
        pass
    else:
        ask = None
    return bid, ask


def _compute_mid(df: pd.DataFrame, bid_col: str | None, ask_col: str | None, close_col: str | None) -> pd.Series:
    if bid_col and ask_col and bid_col in df.columns and ask_col in df.columns:
        return (df[bid_col] + df[ask_col]) / 2
    if close_col and close_col in df.columns:
        return df[close_col]
    raise ValueError("No mid price available: need bid/ask or close column")


def _forward_return(
    df: pd.DataFrame,
    params: dict,
    price_context: dict | None,
) -> pd.DataFrame:
    result = df.copy()
    ohlcv_map = (price_context or {}).get("ohlcv_map", {})
    bid_col, ask_col = _resolve_bid_ask(result, price_context)
    close_col = _get_close_col(result, ohlcv_map)

    periods = int(params.get("periods", params.get("T", 5)))
    mode = params.get("mode", params.get("output_type", "regression"))

    mid = _compute_mid(result, bid_col, ask_col, close_col)
    mid_fwd = mid.shift(-periods)
    mid_return = (mid_fwd - mid) / mid

    if mode == "regression":
        result["label"] = mid_return
        return result

    framing = params.get("framing", "mid_price_direction")

    if framing == "execution_aware":
        if not bid_col or not ask_col:
            raise ValueError(
                "Execution-aware labeling requires best_bid and best_ask columns. "
                "Use Mid Price Direction or upload order book data."
            )
        direction = params.get("direction", "long")
        min_profit = float(params.get("min_profit_threshold", 0.001))
        bid = result[bid_col]
        ask = result[ask_col]

        if direction in ("long", "both"):
            long_return = (bid.shift(-periods) - ask) / ask
            # NaN (not 0) where the forward window runs past the data end, so
            # these unknowable rows are dropped rather than labeled "unprofitable".
            result["label_long"] = np.where(
                long_return.isna(), np.nan, (long_return > min_profit).astype(float)
            )

        if direction in ("short", "both"):
            short_return = (bid - ask.shift(-periods)) / bid
            result["label_short"] = np.where(
                short_return.isna(), np.nan, (short_return > min_profit).astype(float)
            )

        if direction == "long":
            result["label"] = result["label_long"]
        elif direction == "short":
            result["label"] = result["label_short"]
        return result

    # Mid price direction (default classification). Rows whose forward window
    # runs past the data end have a NaN return and must stay NaN — labeling them
    # Flat (0) would inject fabricated "no move" samples at the series tail.
    up_threshold = float(params.get("up_threshold", 0.005))
    down_threshold = float(params.get("down_threshold", -0.005))
    result["label"] = np.where(
        mid_return.isna(),
        np.nan,
        np.where(mid_return > up_threshold, 1.0, np.where(mid_return < down_threshold, -1.0, 0.0)),
    )
    return result


def _triple_barrier_simple(
    df: pd.DataFrame,
    params: dict,
    ref_prices: np.ndarray,
) -> np.ndarray:
    tp = float(params.get("tp", 0.02))
    sl = float(params.get("sl", 0.02))
    max_periods = int(params.get("max_periods", 10))
    n = len(ref_prices)
    labels = np.zeros(n)

    for i in range(n):
        entry = ref_prices[i]
        if np.isnan(entry) or entry == 0:
            labels[i] = np.nan
            continue
        upper = entry * (1 + tp)
        lower = entry * (1 - sl)
        label = 0
        end = min(i + max_periods + 1, n)
        for j in range(i + 1, end):
            price = ref_prices[j]
            if np.isnan(price):
                continue
            if price >= upper:
                label = 1
                break
            if price <= lower:
                label = -1
                break
        # A "0" (no barrier hit) is only trustworthy over a *full* horizon. Near
        # the end of the series the window is truncated, so an untouched barrier
        # is unknown, not a genuine timeout → NaN so the row is dropped.
        if label == 0 and (end - (i + 1)) < max_periods:
            labels[i] = np.nan
        else:
            labels[i] = label
    return labels


def _triple_barrier_realistic(
    df: pd.DataFrame,
    params: dict,
    bid_col: str,
    ask_col: str,
) -> np.ndarray:
    tp = float(params.get("tp", 0.02))
    sl = float(params.get("sl", 0.02))
    max_periods = int(params.get("max_periods", 10))

    bid = df[bid_col].values
    ask = df[ask_col].values
    n = len(bid)
    labels = np.zeros(n)

    for i in range(n):
        entry = ask[i]
        if np.isnan(entry) or entry == 0:
            labels[i] = np.nan
            continue
        upper = entry * (1 + tp)
        lower = entry * (1 - sl)
        label = 0
        end = min(i + max_periods + 1, n)
        for j in range(i + 1, end):
            b = bid[j]
            if np.isnan(b):
                continue
            if b >= upper:
                label = 1
                break
            if b <= lower:
                label = -1
                break
        # Truncated horizon at the series tail → an untouched barrier is unknown.
        if label == 0 and (end - (i + 1)) < max_periods:
            labels[i] = np.nan
        else:
            labels[i] = label
    return labels


def _triple_barrier(
    df: pd.DataFrame,
    params: dict,
    price_context: dict | None,
) -> pd.DataFrame:
    result = df.copy()
    ohlcv_map = (price_context or {}).get("ohlcv_map", {})
    bid_col, ask_col = _resolve_bid_ask(result, price_context)
    close_col = _get_close_col(result, ohlcv_map)
    mode = params.get("barrier_mode", params.get("mode", "simple"))

    if mode == "realistic":
        if not bid_col or not ask_col:
            raise ValueError(
                "Realistic triple barrier requires best_bid and best_ask columns."
            )
        result["label"] = _triple_barrier_realistic(result, params, bid_col, ask_col)
        return result

    mid = _compute_mid(result, bid_col, ask_col, close_col)
    result["label"] = _triple_barrier_simple(result, params, mid.values)
    return result


def _custom_label(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    result = df.copy()
    expression = params.get("expression", "")
    if not expression.strip():
        raise ValueError("Custom label expression is required")

    local_dict = {
        str(c): result[c] for c in result.columns if pd.api.types.is_numeric_dtype(result[c])
    }
    for role in ("open", "high", "low", "close", "volume", "bid", "ask"):
        for c in result.columns:
            norm = str(c).lower()
            if role in norm:
                local_dict[role] = result[c]

    evaluated = pd.eval(expression, local_dict=local_dict)
    if isinstance(evaluated, pd.Series):
        result["label"] = evaluated.astype(float)
    else:
        result["label"] = float(evaluated)
    return result


def _drop_label_na(df: pd.DataFrame) -> pd.DataFrame:
    label_cols = [c for c in LABEL_COLUMNS if c in df.columns]
    if not label_cols:
        return df
    return df.dropna(subset=label_cols, how="all")


def apply_label(
    df: pd.DataFrame,
    label_config: dict | None,
    price_context: dict | None = None,
) -> tuple[pd.DataFrame | None, str | None]:
    if not label_config:
        return df, None

    method = label_config.get("method")
    params = label_config.get("params") or {}

    try:
        if method == "forward_return":
            result = _forward_return(df, params, price_context)
        elif method == "triple_barrier":
            result = _triple_barrier(df, params, price_context)
        elif method == "custom":
            result = _custom_label(df, params)
        else:
            return None, f"Unknown label method: {method}"

        result = _drop_label_na(result)
        return result, None
    except Exception as e:
        return None, str(e)
