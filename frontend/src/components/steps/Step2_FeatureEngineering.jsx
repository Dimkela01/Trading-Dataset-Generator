import { useState } from 'react'
import './Steps.css'

const INDICATORS = [
  { type: 'rsi', name: 'RSI', desc: 'Relative Strength Index', params: [{ key: 'period', default: 14, label: 'Period' }] },
  { type: 'macd', name: 'MACD', desc: 'Moving Average Convergence Divergence', params: [
    { key: 'fast', default: 12 }, { key: 'slow', default: 26 }, { key: 'signal', default: 9 },
  ]},
  { type: 'bbands', name: 'Bollinger Bands', desc: 'Volatility bands around price', params: [
    { key: 'period', default: 20 }, { key: 'std', default: 2 },
  ]},
  { type: 'atr', name: 'ATR', desc: 'Average True Range', params: [{ key: 'period', default: 14 }] },
  { type: 'vwap', name: 'VWAP', desc: 'Volume-weighted average price (needs volume)', params: [] },
  { type: 'lag', name: 'Lag', desc: 'Shift column by N periods', params: [
    { key: 'column', default: 'close', label: 'Column' },
    { key: 'periods', default: 1, label: 'Periods' },
  ]},
  { type: 'ratio', name: 'Ratio', desc: 'Divide column A by B', params: [
    { key: 'col_a', default: 'close' }, { key: 'col_b', default: 'volume' },
  ]},
  { type: 'diff', name: 'Diff', desc: 'Subtract column B from A', params: [
    { key: 'col_a', default: 'high' }, { key: 'col_b', default: 'low' },
  ]},
]

const numericCols = (uploadData) =>
  uploadData.columns.filter((c) => c.detected_type !== 'timestamp').map((c) => c.name)

export default function Step2_FeatureEngineering({ uploadData, pipelineState, setPipelineState }) {
  const [selected, setSelected] = useState('rsi')
  const [params, setParams] = useState({ period: 14 })
  const cols = numericCols(uploadData)

  const indicator = INDICATORS.find((i) => i.type === selected)

  const addFeature = () => {
    setPipelineState((s) => ({
      ...s,
      features: [...(s.features || []), { type: selected, params: { ...params } }],
    }))
  }

  const removeFeature = (idx) => {
    setPipelineState((s) => ({
      ...s,
      features: s.features.filter((_, i) => i !== idx),
    }))
  }

  const onSelectIndicator = (type) => {
    setSelected(type)
    const ind = INDICATORS.find((i) => i.type === type)
    const defaults = {}
    ind?.params.forEach((p) => {
      defaults[p.key] = p.key === 'column' ? (cols[0] || 'close') : p.default
    })
    setParams(defaults)
  }

  return (
    <div className="step-panel">
      <h2>Feature Engineering</h2>

      <div className="feature-layout">
        <div className="feature-list">
          <h3>Added Features</h3>
          {(pipelineState.features || []).length === 0 && (
            <p className="muted">No features added yet</p>
          )}
          {(pipelineState.features || []).map((f, i) => (
            <div key={i} className="feature-item">
              <span className="mono">{f.type}</span>
              <span className="muted">{JSON.stringify(f.params)}</span>
              <button type="button" onClick={() => removeFeature(i)}>×</button>
            </div>
          ))}
        </div>

        <div className="add-feature-panel">
          <h3>Add Feature</h3>
          <select value={selected} onChange={(e) => onSelectIndicator(e.target.value)}>
            {INDICATORS.map((i) => (
              <option key={i.type} value={i.type}>{i.name}</option>
            ))}
          </select>

          <div className="param-inputs">
            {indicator?.params.map((p) => (
              <label key={p.key}>
                {p.label || p.key}
                {p.key === 'column' || p.key === 'col_a' || p.key === 'col_b' ? (
                  <select
                    value={params[p.key] ?? cols[0]}
                    onChange={(e) => setParams({ ...params, [p.key]: e.target.value })}
                  >
                    {cols.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    type={typeof p.default === 'number' ? 'number' : 'text'}
                    value={params[p.key] ?? p.default}
                    onChange={(e) =>
                      setParams({
                        ...params,
                        [p.key]: typeof p.default === 'number' ? parseFloat(e.target.value) : e.target.value,
                      })
                    }
                  />
                )}
              </label>
            ))}
          </div>

          <button type="button" className="primary" onClick={addFeature}>ADD →</button>
        </div>
      </div>

      <div className="indicator-cards">
        {INDICATORS.map((ind) => (
          <div
            key={ind.type}
            className={`indicator-card ${selected === ind.type ? 'selected' : ''}`}
            onClick={() => onSelectIndicator(ind.type)}
            onKeyDown={() => {}}
            role="button"
            tabIndex={0}
          >
            <strong>{ind.name}</strong>
            <p>{ind.desc}</p>
            <span className="hint mono">
              {ind.params.map((p) => `${p.key}=${p.default}`).join(', ') || 'no params'}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
