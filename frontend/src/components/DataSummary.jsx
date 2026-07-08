import './DataSummary.css'

function TypeBadge({ type }) {
  const cls = `badge badge-${type === 'price' ? 'price' : type === 'volume' ? 'volume' : type === 'timestamp' ? 'timestamp' : 'unknown'}`
  return <span className={cls}>{type}</span>
}

export default function DataSummary({ data, onBegin }) {
  const cols = Object.keys(data.preview[0] || {})

  return (
    <div className="data-summary">
      <div className="summary-grid">
        <div className="stats-col">
          <div className="chips">
            <div className="chip">
              <span className="chip-label">Rows</span>
              <span className="chip-value">{data.row_count.toLocaleString()}</span>
            </div>
            <div className="chip">
              <span className="chip-label">Granularity</span>
              <span className="chip-value">{data.granularity}</span>
            </div>
            <div className="chip">
              <span className="chip-label">Timestamp</span>
              <span className="chip-value">{data.timestamp_column || '—'}</span>
            </div>
            <div className="chip">
              <span className="chip-label">Gaps</span>
              <span className="chip-value" style={{ color: data.gaps_detected > 0 ? 'var(--negative)' : 'var(--positive)' }}>
                {data.gaps_detected}
              </span>
            </div>
            <div className="chip">
              <span className="chip-label">Duplicates</span>
              <span className="chip-value">{data.duplicate_rows}</span>
            </div>
            <div className="chip">
              <span className="chip-label">OHLCV</span>
              <span className="chip-value">{data.has_ohlcv ? 'YES' : 'NO'}</span>
            </div>
          </div>

          <div className="column-list">
            <h3>Columns</h3>
            {data.columns.map((col) => (
              <div key={col.name} className="col-row">
                <span className="mono col-name">{col.name}</span>
                <TypeBadge type={col.detected_type} />
                <span className="col-dtype">{col.dtype}</span>
                <div className="missing-bar">
                  <div className="missing-fill" style={{ width: `${col.missing_pct}%` }} />
                </div>
                <span className="missing-pct">{col.missing_pct}%</span>
              </div>
            ))}
          </div>
        </div>

        <div className="preview-col">
          <h3 className="mono" style={{ color: 'var(--accent)', marginBottom: 12 }}>Preview</h3>
          <div className="preview-scroll">
            <table>
              <thead>
                <tr>
                  {cols.map((c) => (
                    <th key={c}>{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.preview.map((row, i) => (
                  <tr key={i}>
                    {cols.map((c) => (
                      <td key={c}>{row[c] != null ? String(row[c]).slice(0, 24) : '—'}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <button className="primary begin-btn" onClick={onBegin}>
        BEGIN PIPELINE →
      </button>
    </div>
  )
}
