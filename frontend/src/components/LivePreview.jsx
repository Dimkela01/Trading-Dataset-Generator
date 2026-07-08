import './LivePreview.css'

export default function LivePreview({ preview, loading, error }) {
  const cols = preview?.columns || []
  const rows = preview?.preview || []

  return (
    <div className="live-preview">
      <div className="preview-header">
        <div className="preview-title-row">
          <h3 className="mono">LIVE PREVIEW</h3>
          {loading && <span className="blink-dot" title="Refreshing" />}
        </div>
        <p className="preview-meta mono">
          {preview?.row_count?.toLocaleString() ?? '—'} rows · {cols.length} columns
        </p>
      </div>

      {error && <div className="preview-error">{error}</div>}

      <div className="preview-table-wrap">
        {cols.length === 0 ? (
          <p className="preview-empty">Configure pipeline to see preview</p>
        ) : (
          <table>
            <thead>
              <tr>
                {cols.map((c) => (
                  <th key={c}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i}>
                  {cols.map((c) => (
                    <td key={c}>
                      {row[c] != null ? String(row[c]).slice(0, 16) : '—'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
