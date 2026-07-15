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
) -> tuple[pd.DataFrame, set[str]]:
    """Derive the transformed columns and report which originals to retire.

    Returns ``(frame, deferred_drops)``. Nothing is removed here: the frame comes
    back with every derived column *added* and every original still present, and
    `deferred_drops` names the columns the caller should remove once the later
    stages have run (see ``pipeline.run_pipeline``).

    Dropping late is what makes the obvious workflow possible — derive a feature
    from a column and *then* discard it. Removing columns here, before features
    and labels exist, means "untick Keep on volume" and "add a close/volume
    ratio" are mutually exclusive, and dropping raw ``close`` would take the
    label's price series with it. Unticking Keep is a statement about the
    *exported* columns, not an instruction to delete the data mid-pipeline.

    A column is retired for two reasons: the user asked to ``drop`` it, or it was
    transformed and the derived column supersedes it. `protected_cols` (the raw
    price/volume/bid/ask columns that later stages resolve by name) are exempt
    from the second case only — an explicit ``drop`` is still honoured.
    """
    result = df.copy()
    protected_cols = protected_cols or set()
    transform_map = {t["column"]: t for t in column_transforms}
    deferred_drops: set[str] = set()

    cols_to_process = [
        c for c in result.columns
        if timestamp_col is None or c != timestamp_col
    ]

    for col in cols_to_process:
        cfg = transform_map.get(col, {"transform": "none", "params": {}})
        transform = cfg.get("transform", "none")
        params = cfg.get("params") or {}

        if transform == "drop":
            deferred_drops.add(col)
            continue

        if transform == "none":
            continue

        if not pd.api.types.is_numeric_dtype(result[col]):
            continue

        new_series = _apply_single(result[col], transform, params)
        if new_series is None:
            continue

        suffix = transform if transform != "pct_change" else f"pct_change_{params.get('periods', 1)}"
        if transform in ("z_score", "rolling_mean", "rolling_std", "rolling_min", "rolling_max"):
            suffix = f"{transform}_{params.get('window', 20)}"
        new_name = f"{col}_{suffix}"
        result[new_name] = new_series
        # The derived column supersedes the original — unless the original is a
        # protected price column that indicators/labels still resolve by name.
        if col not in protected_cols:
            deferred_drops.add(col)

    return result, deferred_drops
