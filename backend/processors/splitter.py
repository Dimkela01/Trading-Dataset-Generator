import pandas as pd


def temporal_split(
    df: pd.DataFrame,
    train_ratio: float,
    embargo: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Chronological train/test split.

    `embargo` purges the last `embargo` rows from the *train* set. Those rows
    carry forward-looking labels (horizon T) that peek into the first test rows,
    so dropping them prevents label leakage across the boundary. Test always
    starts at the cutoff; the purged rows are simply discarded.
    """
    train_ratio = max(0.0, min(1.0, float(train_ratio)))
    embargo = max(0, int(embargo))
    n = len(df)
    cutoff = int(n * train_ratio)
    if cutoff <= 0:
        cutoff = 1
    if cutoff >= n:
        cutoff = n - 1

    train_end = cutoff - embargo
    if train_end < 1:  # embargo can't erase the whole train set
        train_end = 1
    train_df = df.iloc[:train_end].copy()
    test_df = df.iloc[cutoff:].copy()
    return train_df, test_df


def walk_forward_split(
    df: pd.DataFrame,
    n_splits: int = 5,
    gap: int = 0,
) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
    n = len(df)
    n_splits = max(1, int(n_splits))
    gap = max(0, int(gap))

    step = max(1, (n - gap) // (n_splits + 1))
    folds: list[tuple[pd.DataFrame, pd.DataFrame]] = []

    for i in range(1, n_splits + 1):
        train_end = step * i
        test_start = train_end + gap
        test_end = min(test_start + step, n)
        if train_end < 1 or test_end <= test_start:
            continue
        folds.append((df.iloc[:train_end].copy(), df.iloc[test_start:test_end].copy()))

    if not folds:
        return [temporal_split(df, 0.8)]
    return folds
