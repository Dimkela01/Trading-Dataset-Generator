import numpy as np
import pandas as pd

TRANSFORM_NAMES = (
    "none",
    "log_return",
    "pct_change",
    "z_score",
    "rolling_mean",
    "rolling_std",
    "rolling_min",
    "rolling_max",
    "drop",
)


def _apply_single(series: pd.Series, transform: str, params: dict) -> pd.Series | None:
    window = int(params.get("window", 20))
    periods = int(params.get("periods", 1))

    if transform == "none":
        return series
    if transform == "drop":
        return None
    if transform == "log_return":
        shifted = series.shift(1)
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.log(series / shifted)
    if transform == "pct_change":
        return series.pct_change(periods=periods)
    if transform == "z_score":
        roll = series.rolling(window=window)
        std = roll.std()
        return (series - roll.mean()) / std.replace(0, np.nan)
    if transform == "rolling_mean":
        return series.rolling(window=window).mean()
    if transform == "rolling_std":
        return series.rolling(window=window).std()
    if transform == "rolling_min":
        return series.rolling(window=window).min()
    if transform == "rolling_max":
        return series.rolling(window=window).max()
    return series


def apply_transforms(
    df: pd.DataFrame,
    column_transforms: list[dict],
    timestamp_col: str | None,
    protected_cols: set[str] | None = None,
) -> pd.DataFrame:
    """Apply per-column transforms.

    `protected_cols` are the raw price/volume/bid/ask columns that downstream
    stages (indicators, labels) resolve *by name* (e.g. ``close``). When a
    protected column is transformed, we keep the original alongside the derived
    column instead of dropping it — otherwise transforming ``close`` would make
    RSI/MACD/labels unable to find their price series. An explicit ``drop`` on a
    protected column is still honoured (the user asked for it).
    """
    result = df.copy()
    protected_cols = protected_cols or set()
    transform_map = {t["column"]: t for t in column_transforms}

    cols_to_process = [
        c for c in result.columns
        if timestamp_col is None or c != timestamp_col
    ]

    for col in cols_to_process:
        cfg = transform_map.get(col, {"transform": "none", "params": {}})
        transform = cfg.get("transform", "none")
        params = cfg.get("params") or {}

        if transform == "drop":
            if col in result.columns:
                result = result.drop(columns=[col])
            continue

        if col not in result.columns:
            continue

        if not pd.api.types.is_numeric_dtype(result[col]):
            continue

        new_series = _apply_single(result[col], transform, params)
        if new_series is not None:
            if transform == "none":
                continue
            suffix = transform if transform != "pct_change" else f"pct_change_{params.get('periods', 1)}"
            if transform in ("z_score", "rolling_mean", "rolling_std", "rolling_min", "rolling_max"):
                suffix = f"{transform}_{params.get('window', 20)}"
            new_name = f"{col}_{suffix}"
            result[new_name] = new_series
            # Drop the original only if it isn't a protected price column that
            # downstream indicators/labels still need to resolve by name.
            if transform != "none" and col not in protected_cols:
                result = result.drop(columns=[col])

    return result
