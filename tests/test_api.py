"""HTTP API integration tests (upload, preview, export, select_asset)."""

import io
import zipfile

import pyarrow.parquet as pq


def test_health(api_client):
    assert api_client.get("/health").json() == {"status": "ok"}


def test_upload_and_preview(uploaded_session, api_client):
    sid = uploaded_session["session_id"]
    state = {
        "session_id": sid,
        "column_transforms": [
            {"column": "close", "transform": "pct_change", "params": {"periods": 1}},
        ],
        "features": [{"type": "rsi", "params": {"period": 14}}],
        "label": None,
        "split": {"method": "temporal", "params": {"train_ratio": 0.8}},
    }
    r = api_client.post("/preview", json=state)
    assert r.status_code == 200
    body = r.json()
    assert body["row_count"] > 0
    assert "rsi_14" in body["columns"]
    assert len(body["preview"]) <= 20


def test_preview_rejects_bad_feature(uploaded_session, api_client):
    sid = uploaded_session["session_id"]
    state = {
        "session_id": sid,
        "column_transforms": [],
        "features": [{"type": "ratio", "params": {"col_a": "close", "col_b": "not_a_column"}}],
    }
    r = api_client.post("/preview", json=state)
    assert r.status_code == 400
    assert "not_a_column" in r.json()["detail"]


def test_preview_offers_pre_drop_columns_to_feature_pickers(uploaded_session, api_client):
    """A dropped column stays selectable as a feature input, but leaves the export.

    This is the contract Step 2's column pickers rely on: they render
    `available_columns`, not `columns`.
    """
    sid = uploaded_session["session_id"]
    state = {
        "session_id": sid,
        "column_transforms": [{"column": "volume", "transform": "drop", "params": {}}],
        "features": [{"type": "vwap", "params": {}}],
    }
    r = api_client.post("/preview", json=state)
    assert r.status_code == 200
    body = r.json()
    assert "vwap" in body["columns"]  # VWAP computed from volume...
    assert "volume" not in body["columns"]  # ...which is gone from the export
    assert "volume" in body["available_columns"]  # ...but still pickable
    assert body["columns_dropped"] == ["volume"]


def test_preview_surfaces_label_error_without_losing_features(uploaded_session, api_client):
    sid = uploaded_session["session_id"]
    state = {
        "session_id": sid,
        "column_transforms": [],
        "features": [{"type": "rsi", "params": {"period": 14}}],
        "label": {"method": "custom", "params": {"expression": "close.to_csv('x')"}},
    }
    r = api_client.post("/preview", json=state)
    assert r.status_code == 200
    body = r.json()
    assert body["label_error"]
    assert "rsi_14" in body["columns"]  # the feature preview survives


def test_export_zip_contents(uploaded_session, api_client):
    sid = uploaded_session["session_id"]
    state = {
        "session_id": sid,
        "column_transforms": [{"column": "volume", "transform": "none", "params": {}}],
        "features": [],
        "label": {
            "method": "forward_return",
            "params": {
                "periods": 5,
                "mode": "classification",
                "framing": "mid_price_direction",
                "up_threshold": 0.005,
                "down_threshold": -0.005,
            },
        },
        "split": {"method": "temporal", "params": {"train_ratio": 0.75}},
    }
    r = api_client.post("/export", json=state)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(z.namelist())
    assert names == {"train.parquet", "test.parquet", "metadata.json", "report.html"}
    train = pq.read_table(io.BytesIO(z.read("train.parquet"))).to_pandas()
    assert "label" in train.columns
    assert "datetime" in train.columns


def test_select_asset_flow(api_client, multi_asset_df):
    buf = io.BytesIO()
    multi_asset_df.to_csv(buf, index=False)
    buf.seek(0)
    r = api_client.post("/upload", files={"file": ("multi.csv", buf.getvalue(), "text/csv")})
    assert r.status_code == 200
    data = r.json()
    assert data["is_multi_asset"] is True

    r2 = api_client.post(
        "/select_asset",
        json={
            "session_id": data["session_id"],
            "symbol_column": data["symbol_column"],
            "symbol_value": "ETHUSDT",
        },
    )
    assert r2.status_code == 200
    filtered = r2.json()
    assert filtered["is_multi_asset"] is False
    assert filtered["row_count"] == multi_asset_df[multi_asset_df["symbol"] == "ETHUSDT"].shape[0]


def test_upload_semicolon_delimited(api_client):
    raw = "day;timestamp;close;volume\n0;2024-01-01;100;10\n1;2024-01-02;101;11\n"
    r = api_client.post(
        "/upload",
        files={"file": ("ticks.csv", raw.encode(), "text/csv")},
    )
    assert r.status_code == 200
    cols = [c["name"] for c in r.json()["columns"]]
    assert "close" in cols
    assert len(cols) >= 3
