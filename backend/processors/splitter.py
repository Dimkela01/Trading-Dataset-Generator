import pandas as pd


def temporal_split(df: pd.DataFrame, train_ratio: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_ratio = max(0.0, min(1.0, float(train_ratio)))
    cutoff = int(len(df) * train_ratio)
    if cutoff <= 0:
        cutoff = 1
    if cutoff >= len(df):
        cutoff = len(df) - 1
    train_df = df.iloc[:cutoff].copy()
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
