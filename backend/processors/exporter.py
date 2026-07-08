import json
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

import numpy as np
import pandas as pd


def build_metadata(
    pipeline_state: dict,
    stats: dict,
    original_filename: str,
) -> dict:
    return {
        "export_timestamp": datetime.now(timezone.utc).isoformat(),
        "original_filename": original_filename,
        "pipeline": {
            "column_transforms": pipeline_state.get("column_transforms", []),
            "features_added": pipeline_state.get("features", []),
            "label_config": pipeline_state.get("label"),
            "split_config": pipeline_state.get("split"),
        },
        "stats": stats,
    }


def _svg_bar_chart(counts: dict, width: int = 400, height: int = 120) -> str:
    labels = list(counts.keys())
    values = [counts[k] for k in labels]
    max_val = max(values) if values else 1
    bar_w = width // max(len(labels), 1) - 10
    bars = []
    for i, (label, val) in enumerate(zip(labels, values)):
        h = int((val / max_val) * (height - 30)) if max_val else 0
        x = 20 + i * (bar_w + 10)
        y = height - 20 - h
        bars.append(f'<rect x="{x}" y="{y}" width="{bar_w}" height="{h}" fill="#f0b429"/>')
        bars.append(f'<text x="{x + bar_w/2}" y="{height - 5}" fill="#6b6b8a" font-size="10" text-anchor="middle">{label}</text>')
        bars.append(f'<text x="{x + bar_w/2}" y="{y - 4}" fill="#e8e8f0" font-size="9" text-anchor="middle">{val}</text>')
    return f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">{"".join(bars)}</svg>'


def _svg_histogram(series: pd.Series, width: int = 400, height: int = 120, bins: int = 20) -> str:
    clean = series.dropna()
    if clean.empty:
        return f'<svg width="{width}" height="{height}"></svg>'
    counts, edges = np.histogram(clean, bins=bins)
    max_val = max(counts) if len(counts) else 1
    bar_w = (width - 40) // bins
    bars = []
    for i, val in enumerate(counts):
        h = int((val / max_val) * (height - 30)) if max_val else 0
        x = 20 + i * bar_w
        y = height - 20 - h
        bars.append(f'<rect x="{x}" y="{y}" width="{bar_w - 2}" height="{h}" fill="#4ade80"/>')
    return f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">{"".join(bars)}</svg>'


def _svg_timeline_split(train_rows: int, test_rows: int, width: int = 500, height: int = 40) -> str:
    total = train_rows + test_rows
    if total == 0:
        return ""
    train_w = int((train_rows / total) * (width - 4))
    test_w = width - 4 - train_w
    return f'''<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
      <rect x="0" y="10" width="{train_w}" height="20" fill="#3b82f6"/>
      <rect x="{train_w}" y="10" width="{test_w}" height="20" fill="#f0b429" opacity="0.6"/>
      <text x="5" y="8" fill="#6b6b8a" font-size="10">Train ({train_rows})</text>
      <text x="{train_w + 5}" y="8" fill="#6b6b8a" font-size="10">Test ({test_rows})</text>
    </svg>'''


def _corr_color(val: float) -> str:
    if np.isnan(val):
        return "#1e1e2e"
    val = max(-1, min(1, val))
    if val < 0:
        intensity = int(abs(val) * 200)
        return f"rgb({max(0, 100-intensity)}, {max(0, 100-intensity)}, {200})"
    if val > 0:
        intensity = int(val * 200)
        return f"rgb({200}, {180 + intensity//4}, {max(0, 100-intensity//2)})"
    return "#e8e8f0"


def _svg_heatmap(corr: pd.DataFrame, cell_size: int = 24) -> str:
    cols = list(corr.columns)
    n = len(cols)
    if n == 0:
        return "<p>No numeric features for correlation heatmap.</p>"
    w = n * cell_size + 120
    h = n * cell_size + 40
    cells = []
    for i, row_col in enumerate(cols):
        for j, col_col in enumerate(cols):
            val = corr.loc[row_col, col_col]
            color = _corr_color(val)
            x = 100 + j * cell_size
            y = 20 + i * cell_size
            cells.append(f'<rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" fill="{color}" stroke="#1e1e2e"/>')
    labels_y = "".join(
        f'<text x="95" y="{20 + i * cell_size + 16}" fill="#6b6b8a" font-size="8" text-anchor="end">{c[:12]}</text>'
        for i, c in enumerate(cols)
    )
    labels_x = "".join(
        f'<text x="{100 + j * cell_size + cell_size/2}" y="15" fill="#6b6b8a" font-size="8" text-anchor="middle" transform="rotate(-45 {100 + j * cell_size + cell_size/2} 15)">{c[:12]}</text>'
        for j, c in enumerate(cols)
    )
    return f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">{labels_x}{labels_y}{"".join(cells)}</svg>'


def generate_report_html(
    filename: str,
    pipeline_state: dict,
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    full_df: pd.DataFrame,
    timestamp_col: str | None,
    label_distribution: dict | None,
    is_classification: bool,
) -> str:
    export_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    label_cols = [c for c in full_df.columns if c == "label" or c.startswith("label_")]
    feature_cols = [
        c for c in full_df.columns
        if c != timestamp_col
        and c not in label_cols
        and pd.api.types.is_numeric_dtype(full_df[c])
    ]
    if len(feature_cols) > 20:
        variances = full_df[feature_cols].var().sort_values(ascending=False)
        feature_cols = list(variances.head(20).index)

    corr_svg = ""
    if len(feature_cols) >= 2:
        corr = full_df[feature_cols].corr()
        corr_svg = _svg_heatmap(corr)

    label_svg = ""
    if label_distribution:
        if isinstance(label_distribution, dict) and "label_long" in label_distribution:
            long_svg = _svg_bar_chart(label_distribution["label_long"])
            short_svg = _svg_bar_chart(label_distribution["label_short"])
            label_svg = (
                '<div style="display:flex;gap:24px;flex-wrap:wrap">'
                f'<div><h3 style="color:#f0b429;font-size:14px">label_long</h3>{long_svg}</div>'
                f'<div><h3 style="color:#f0b429;font-size:14px">label_short</h3>{short_svg}</div>'
                "</div>"
            )
        elif is_classification and isinstance(label_distribution, dict):
            label_svg = _svg_bar_chart(label_distribution)
        elif "label" in full_df.columns:
            label_svg = _svg_histogram(full_df["label"])

    transforms_rows = "".join(
        f"<tr><td>{t.get('column')}</td><td>{t.get('transform')}</td><td>{json.dumps(t.get('params', {}))}</td></tr>"
        for t in pipeline_state.get("column_transforms", [])
    )
    features_rows = "".join(
        f"<tr><td>{f.get('type')}</td><td>{json.dumps(f.get('params', {}))}</td></tr>"
        for f in pipeline_state.get("features", [])
    )
    dtype_rows = "".join(
        f"<tr><td>{c}</td><td>{full_df[c].dtype}</td></tr>"
        for c in full_df.columns
    )

    label_cfg = pipeline_state.get("label") or {}
    split_cfg = pipeline_state.get("split") or {}

    timeline_svg = _svg_timeline_split(len(train_df), len(test_df))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>AlphaForge Export Report — {filename}</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; background: #0a0a0f; color: #e8e8f0; margin: 0; padding: 24px; }}
  h1, h2 {{ color: #f0b429; font-weight: 600; }}
  h2 {{ border-bottom: 1px solid #1e1e2e; padding-bottom: 8px; margin-top: 32px; }}
  .meta {{ color: #6b6b8a; font-size: 14px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 13px; }}
  th, td {{ border: 1px solid #1e1e2e; padding: 8px 12px; text-align: left; }}
  th {{ background: #141420; color: #f0b429; }}
  tr:nth-child(even) {{ background: #0f0f1a; }}
  .section {{ margin-bottom: 24px; }}
  .chart {{ margin: 16px 0; overflow-x: auto; }}
</style>
</head>
<body>
<h1>AlphaForge Export Report</h1>
<p class="meta">Dataset: <strong>{filename}</strong> · Exported: {export_ts}</p>
<p class="meta">Total rows: {len(full_df)} · Train: {len(train_df)} · Test: {len(test_df)} · Features: {len(feature_cols)}</p>

<h2>Pipeline Summary</h2>
<div class="section">
  <p><strong>Label method:</strong> {label_cfg.get('method', 'none')} · <strong>Split:</strong> {split_cfg.get('method', 'temporal')}</p>
  <h3>Column Transforms</h3>
  <table><tr><th>Column</th><th>Transform</th><th>Params</th></tr>{transforms_rows or '<tr><td colspan="3">None</td></tr>'}</table>
  <h3>Features Added</h3>
  <table><tr><th>Type</th><th>Params</th></tr>{features_rows or '<tr><td colspan="2">None</td></tr>'}</table>
</div>

<h2>Feature List</h2>
<table><tr><th>Column</th><th>Dtype</th></tr>{dtype_rows}</table>

<h2>Label Distribution</h2>
<div class="chart">{label_svg or '<p>No label column.</p>'}</div>

<h2>Train / Test Split</h2>
<div class="chart">{timeline_svg}</div>

<h2>Feature Correlation Heatmap</h2>
<div class="chart">{corr_svg}</div>

<footer style="margin-top:48px;color:#3a3a5a;font-size:12px;">Generated by AlphaForge</footer>
</body>
</html>"""


def build_zip(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    metadata: dict,
    report_html: str,
) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        train_buf = BytesIO()
        test_buf = BytesIO()
        train_df.to_parquet(train_buf, engine="pyarrow", index=False)
        test_df.to_parquet(test_buf, engine="pyarrow", index=False)
        zf.writestr("train.parquet", train_buf.getvalue())
        zf.writestr("test.parquet", test_buf.getvalue())
        zf.writestr("metadata.json", json.dumps(metadata, indent=2, default=str))
        zf.writestr("report.html", report_html)
    buf.seek(0)
    return buf.getvalue()


def compute_label_distribution(df: pd.DataFrame, label_config: dict | None) -> tuple[dict | None, bool]:
    params = (label_config or {}).get("params") or {}
    method = (label_config or {}).get("method", "")

    if "label_long" in df.columns and "label_short" in df.columns:
        dist = {}
        for col in ("label_long", "label_short"):
            vc = df[col].dropna().value_counts().to_dict()
            dist[col] = {str(k): int(v) for k, v in vc.items()}
        return dist, True

    if "label" not in df.columns:
        return None, False

    labels = df["label"].dropna()
    mode = params.get("mode", params.get("output_type", "regression"))
    framing = params.get("framing", "")
    barrier_mode = params.get("barrier_mode", params.get("mode", "simple"))

    is_classification = (
        method == "triple_barrier"
        or mode == "classification"
        or framing in ("mid_price_direction", "execution_aware")
        or (method == "triple_barrier" and barrier_mode in ("simple", "realistic"))
    )

    if method == "triple_barrier":
        is_classification = True

    if method == "forward_return" and mode == "regression":
        is_classification = False

    if is_classification:
        vc = labels.value_counts().to_dict()
        return {str(k): int(v) for k, v in vc.items()}, True
    return {
        "mean": float(labels.mean()),
        "std": float(labels.std()),
        "min": float(labels.min()),
        "max": float(labels.max()),
    }, False
