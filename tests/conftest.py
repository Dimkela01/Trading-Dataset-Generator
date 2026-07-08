"""Shared fixtures for AlphaForge backend tests."""

import io
import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

# Backend modules live in backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

SAMPLE_CSV = Path(__file__).resolve().parent.parent / "sample_data" / "btc_1h.csv"


@pytest.fixture
def ohlcv_df() -> pd.DataFrame:
    return pd.read_csv(SAMPLE_CSV)


@pytest.fixture
def order_book_df(ohlcv_df) -> pd.DataFrame:
    df = ohlcv_df.copy()
    df["best_bid"] = df["close"] - 5.0
    df["best_ask"] = df["close"] + 5.0
    return df


@pytest.fixture
def multi_asset_df(ohlcv_df) -> pd.DataFrame:
    """Large enough multi-asset file to trigger symbol detection (n_unique < 1% of rows)."""
    parts = []
    for sym in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        chunk = ohlcv_df.copy()
        chunk["symbol"] = sym
        parts.append(chunk)
    # Repeat to exceed 300 rows so 3 symbols < 1% of row count fails - need n_unique < n*0.01
    # 3 < n*0.01 => n > 300. 72*5 = 360 rows, 3 symbols => 3 < 3.6 True
    big = pd.concat(parts * 5, ignore_index=True)
    return big


@pytest.fixture
def api_client():
    import main as main_module

    main_module.sessions.clear()
    client = TestClient(main_module.app)
    yield client
    main_module.sessions.clear()


@pytest.fixture
def uploaded_session(api_client, ohlcv_df):
    buf = io.BytesIO()
    ohlcv_df.to_csv(buf, index=False)
    buf.seek(0)
    r = api_client.post("/upload", files={"file": ("btc_1h.csv", buf.getvalue(), "text/csv")})
    assert r.status_code == 200
    return r.json()
