import { useEffect, useMemo } from 'react'
import './Steps.css'

const TRANSFORMS = [
  'none',
  'log_return',
  'pct_change',
  'z_score',
  'rolling_mean',
  'rolling_std',
  'rolling_min',
  'rolling_max',
]

const NEEDS_WINDOW = ['z_score', 'rolling_mean', 'rolling_std', 'rolling_min', 'rolling_max']
const NEEDS_PERIODS = ['pct_change']

export default function Step1_ColumnManager({ uploadData, pipelineState, setPipelineState }) {
  const tsCol = uploadData.timestamp_column
  const dataCols = useMemo(
    () => uploadData.columns.filter((c) => c.name !== tsCol),
    [uploadData.columns, tsCol],
  )

  useEffect(() => {
    if (pipelineState.column_transforms?.length > 0) return
    const initial = dataCols.map((c) => ({
      column: c.name,
      transform: 'none',
      params: {},
      keep: true,
    }))
    setPipelineState((s) => ({
      ...s,
      column_transforms: initial.map(({ column, transform, params }) => ({
        column,
        transform,
        params,
      })),
    }))
  }, [dataCols, pipelineState.column_transforms, setPipelineState])

  const rows = dataCols.map((col) => {
    const cfg = pipelineState.column_transforms.find((t) => t.column === col.name) || {
      column: col.name,
      transform: 'none',
      params: {},
    }
    const keep = cfg.transform !== 'drop'
    return { ...col, ...cfg, keep }
  })

  const updateRow = (colName, updates) => {
    setPipelineState((s) => {
      const transforms = [...(s.column_transforms || [])]
      const idx = transforms.findIndex((t) => t.column === colName)
      const existing = idx >= 0 ? transforms[idx] : { column: colName, transform: 'none', params: {} }
      const merged = { ...existing, ...updates }
      if (updates.keep === false) merged.transform = 'drop'
      if (updates.keep === true && merged.transform === 'drop') merged.transform = 'none'
      if (idx >= 0) transforms[idx] = merged
      else transforms.push(merged)
      return { ...s, column_transforms: transforms }
    })
  }

  const selectAll = () => {
    setPipelineState((s) => ({
      ...s,
      column_transforms: dataCols.map((c) => {
        const existing = s.column_transforms.find((t) => t.column === c.name)
        return {
          column: c.name,
          transform: existing?.transform === 'drop' ? 'none' : existing?.transform || 'none',
          params: existing?.params || {},
        }
      }),
    }))
  }

  const dropUnknowns = () => {
    setPipelineState((s) => ({
      ...s,
      column_transforms: dataCols.map((c) => {
        const existing = s.column_transforms.find((t) => t.column === c.name)
        const isUnknown = c.detected_type === 'unknown'
        return {
          column: c.name,
          transform: isUnknown ? 'drop' : existing?.transform || 'none',
          params: existing?.params || {},
        }
      }),
    }))
  }

  return (
    <div className="step-panel">
      <h2>Column Manager</h2>
      <p className="step-desc">Transform or drop columns. Timestamp column is preserved automatically.</p>

      <div className="quick-actions">
        <button type="button" onClick={selectAll}>SELECT ALL</button>
        <button type="button" onClick={dropUnknowns}>DROP UNKNOWNS</button>
      </div>

      <table className="step-table">
        <thead>
          <tr>
            <th>Keep</th>
            <th>Column</th>
            <th>Type</th>
            <th>Transform</th>
            <th>Params</th>
            <th>Missing</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.name}>
              <td>
                <input
                  type="checkbox"
                  checked={row.keep}
                  onChange={(e) => updateRow(row.name, { keep: e.target.checked })}
                />
              </td>
              <td className="mono">{row.name}</td>
              <td>
                <span className={`badge badge-${row.detected_type === 'price' ? 'price' : row.detected_type === 'volume' ? 'volume' : 'unknown'}`}>
                  {row.detected_type}
                </span>
              </td>
              <td>
                <select
                  value={row.keep ? row.transform : 'drop'}
                  disabled={!row.keep}
                  onChange={(e) => updateRow(row.name, { transform: e.target.value })}
                >
                  {TRANSFORMS.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                  <option value="drop">drop</option>
                </select>
              </td>
              <td>
                {NEEDS_WINDOW.includes(row.transform) && (
                  <input
                    type="number"
                    min={2}
                    value={row.params?.window ?? 20}
                    onChange={(e) =>
                      updateRow(row.name, {
                        params: { ...row.params, window: parseInt(e.target.value, 10) },
                      })
                    }
                    style={{ width: 60 }}
                  />
                )}
                {NEEDS_PERIODS.includes(row.transform) && (
                  <input
                    type="number"
                    min={1}
                    value={row.params?.periods ?? 1}
                    onChange={(e) =>
                      updateRow(row.name, {
                        params: { ...row.params, periods: parseInt(e.target.value, 10) },
                      })
                    }
                    style={{ width: 60 }}
                  />
                )}
              </td>
              <td>
                <div className="missing-bar inline">
                  <div className="missing-fill" style={{ width: `${row.missing_pct}%` }} />
                </div>
                <span className="missing-pct">{row.missing_pct}%</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
