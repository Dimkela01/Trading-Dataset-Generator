import ast

import numpy as np
import pandas as pd

LABEL_COLUMNS = ("label", "label_long", "label_short")

# Roles a custom expression may use when the file doesn't name its columns that
# way (e.g. a "px_last" column reachable as `close`). Resolved through the
# detector's mapping — never by scanning column names for a substring.
_EXPRESSION_ROLES = ("open", "high", "low", "close", "volume", "bid", "ask")

# Bare functions an expression may call.
_ALLOWED_FUNCS = {
    "abs": np.abs,
    "log": np.log,
    "log1p": np.log1p,
    "exp": np.exp,
    "sqrt": np.sqrt,
    "sign": np.sign,
    "minimum": np.minimum,
    "maximum": np.maximum,
    "where": np.where,
}

# Methods an expression may call on a column. Allowlisted because `pd.eval` is
# not a sandbox: it executes arbitrary method calls, so `close.to_csv('...')`
# writes a file to the host and `close.__class__` walks out of the namespace.
_ALLOWED_METHODS = frozenset(
    {
        "shift", "diff", "pct_change", "abs", "clip", "fillna", "round",
        "rolling", "ewm", "cumsum", "cumprod", "rank", "notna", "isna",
        "mean", "std", "var", "median", "sum", "min", "max", "quantile",
    }
)

# Syntax an expression may use. Anything absent — subscripts, lambdas,
# comprehensions, assignments, imports — is rejected before evaluation.
_ALLOWED_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Compare, ast.Call,
    ast.Attribute, ast.Name, ast.Constant, ast.Load, ast.keyword,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.BitAnd, ast.BitOr, ast.BitXor, ast.Invert,
    ast.USub, ast.UAdd, ast.Not,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
)


def _expression_namespace(df: pd.DataFrame, price_context: dict | None) -> dict:
    """Names a custom expression may reference, bound to their series.

    Real column names bind to themselves and always win — a column literally
    named ``close`` is what the user means by ``close``. Role aliases only fill
    gaps, and resolve through the detector's OHLCV/bid/ask mapping.

    The mapping matters: matching roles by substring binds ``close`` to a
    derived ``close_log_return`` whenever one exists, so an expression like
    ``close.shift(-5) > close * 1.02`` silently compares log returns and yields a
    plausible-looking but entirely wrong label.
    """
    ctx = price_context or {}
    ohlcv_map = ctx.get("ohlcv_map") or {}

    namespace = {
        str(c): df[c] for c in df.columns if pd.api.types.is_numeric_dtype(df[c])
    }

    role_cols = {r: ohlcv_map[r] for r in _EXPRESSION_ROLES if ohlcv_map.get(r)}
    if ctx.get("bid_column"):
        role_cols["bid"] = ctx["bid_column"]
    if ctx.get("ask_column"):
        role_cols["ask"] = ctx["ask_column"]

    for role, col in role_cols.items():
        if role in namespace:
            continue
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
            namespace[role] = df[col]

    return namespace


def _validate_expression(expression: str, allowed_names: set[str]) -> ast.Expression:
    """Parse an expression and reject anything outside the allowlists."""
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"Could not parse expression: {e.msg}") from None

    for node in ast.walk(tree):
        if isinstance(node, ast.BoolOp):
            raise ValueError(
                "Use '&' and '|' (not 'and'/'or') to combine conditions, "
                "and bracket each side: (a > 1) & (b < 2)"
            )
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(
                f"{type(node).__name__} is not allowed in a label expression"
            )
        if isinstance(node, ast.Attribute) and node.attr not in _ALLOWED_METHODS:
            raise ValueError(
                f"'.{node.attr}' is not allowed in a label expression. "
                f"Allowed: {', '.join(sorted(_ALLOWED_METHODS))}"
            )
        if isinstance(node, ast.Name) and node.id not in allowed_names:
            raise ValueError(
                f"Unknown name '{node.id}'. Available columns: "
                f"{', '.join(sorted(allowed_names))}"
            )
    return tree


def predicted_label_columns(label_config: dict | None) -> list[str]:
    """Column names ``apply_label`` will write for this config.

    Callers use this to detect a collision with a column the user's file
    already contains (e.g. a pre-existing ``label``) before it gets overwritten.
    """
    if not label_config:
        return []
    method = label_config.get("method")
    params = label_config.get("params") or {}

    if method == "forward_return":
        mode = params.get("mode", params.get("output_type", "regression"))
        framing = params.get("framing", "mid_price_direction")
        if mode == "classification" and framing == "execution_aware":
            direction = params.get("direction", "long")
            if direction == "long":
                return ["label_long", "label"]
            if direction == "short":
                return ["label_short", "label"]
            return ["label_long", "label_short"]
        return ["label"]
    # triple_barrier and custom both write a single "label".
    return ["label"]


def _free_name(taken: set[str], base: str) -> str:
    name = f"{base}_source"
    i = 2
    while name in taken:
        name = f"{base}_source_{i}"
        i += 1
    return name


def _preserve_colliding(
    df: pd.DataFrame, predicted: list[str]
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Rename any user column that a generated label would overwrite.

    A file that already has a ``label`` column must not lose it when AlphaForge
    generates its own — the original is preserved as ``label_source`` so the
    generated label can take the canonical name.
    """
    existing = set(df.columns.astype(str))
    to_rename: dict[str, str] = {}
    for col in predicted:
        if col in existing:
            to_rename[col] = _free_name(existing | set(to_rename.values()), col)
    if to_rename:
        df = df.rename(columns=to_rename)
    return df, to_rename


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


def _custom_label(
    df: pd.DataFrame,
    params: dict,
    price_context: dict | None = None,
) -> pd.DataFrame:
    result = df.copy()
    expression = (params.get("expression") or "").strip()
    if not expression:
        raise ValueError("Custom label expression is required")

    namespace = _expression_namespace(result, price_context)
    tree = _validate_expression(expression, set(namespace) | set(_ALLOWED_FUNCS))

    try:
        evaluated = eval(  # noqa: S307 — AST allowlisted above, no builtins
            compile(tree, "<label expression>", "eval"),
            {"__builtins__": {}},
            {**_ALLOWED_FUNCS, **namespace},
        )
    except Exception as e:
        raise ValueError(f"Expression failed: {e}") from None

    if isinstance(evaluated, pd.Series):
        result["label"] = evaluated.astype(float)
    elif isinstance(evaluated, np.ndarray):
        if evaluated.shape != (len(result),):
            raise ValueError(
                f"Expression produced {evaluated.shape[0]} values for "
                f"{len(result)} rows — it must return one value per row."
            )
        result["label"] = evaluated.astype(float)
    elif np.isscalar(evaluated):
        # A constant is almost always a mistake (e.g. comparing two aggregates),
        # but it's a valid frame-wide label, so allow it.
        result["label"] = float(evaluated)
    else:
        raise ValueError(
            "Expression must produce one value per row (a column), not "
            f"{type(evaluated).__name__}."
        )
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

    # Preserve any user column the generated label would clobber (e.g. a
    # pre-existing "label") by renaming it to "<name>_source" first.
    df, _ = _preserve_colliding(df, predicted_label_columns(label_config))

    try:
        if method == "forward_return":
            result = _forward_return(df, params, price_context)
        elif method == "triple_barrier":
            result = _triple_barrier(df, params, price_context)
        elif method == "custom":
            result = _custom_label(df, params, price_context)
        else:
            return None, f"Unknown label method: {method}"

        result = _drop_label_na(result)
        return result, None
    except Exception as e:
        return None, str(e)
