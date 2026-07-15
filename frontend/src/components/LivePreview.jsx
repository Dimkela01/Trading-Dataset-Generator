import './LivePreview.css'

function colClass(col, originalSet, labelSet) {
  if (labelSet.has(col)) return 'col-label'
  if (!originalSet.has(col)) return 'col-new'
  return ''
}

export default function LivePreview({ preview, loading, error, originalColumns = [] }) {
  const cols = preview?.columns || []
  const rows = preview?.preview || []
  const warmup = preview?.warmup_rows || 0
  const rawCount = preview?.row_count
  const finalCount = preview?.final_row_count
  const dropped = rawCount != null && finalCount != null && finalCount !== rawCount

  const originalSet = new Set(originalColumns)
  const labelSet = new Set(preview?.label_columns || [])
  const hasNew = cols.some((c) => !originalSet.has(c) && !labelSet.has(c))
  const hasLabel = labelSet.size > 0 && cols.some((c) => labelSet.has(c))

  return (
    <div className="live-preview">
      <div className="preview-header">
        <div className="preview-title-row">
          <h3 className="mono">LIVE PREVIEW</h3>
          {loading && <span className="blink-dot" title="Refreshing" />}
        </div>
        <p className="preview-meta mono">
          {dropped ? (
            <span title="Rows drop after warm-up and forward-label NaNs are removed on export">
              {rawCount.toLocaleString()} → {finalCount.toLocaleString()} rows after cleaning
            </span>
          ) : (
            <>{rawCount?.toLocaleString() ?? '—'} rows</>
          )}{' '}
          · {cols.length} columns
        </p>
      </div>

      {error && <div className="preview-error">{error}</div>}

      {warmup > 0 && (
        <p className="preview-warmup">
          Skipping {warmup.toLocaleString()} indicator warm-up row{warmup > 1 ? 's' : ''} (still
          filling) — showing the first populated rows.
        </p>
      )}

      {(hasNew || hasLabel) && (
        <div className="preview-legend mono">
          {hasNew && (
            <span className="legend-item">
              <span className="legend-swatch col-new-swatch" /> new column
            </span>
          )}
          {hasLabel && (
            <span className="legend-item">
              <span className="legend-swatch col-label-swatch" /> label
            </span>
          )}
        </div>
      )}

      <div className="preview-table-wrap">
        {cols.length === 0 ? (
          <p className="preview-empty">Configure pipeline to see preview</p>
        ) : (
          <table>
            <thead>
              <tr>
                {cols.map((c) => (
                  <th key={c} className={colClass(c, originalSet, labelSet)}>
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i}>
                  {cols.map((c) => (
                    <td key={c} className={colClass(c, originalSet, labelSet)}>
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
