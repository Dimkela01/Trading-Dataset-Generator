import { useState } from 'react'
import './Steps.css'

// Indicators that run on a single price series which AlphaForge resolves
// automatically (prefers mid price). These have no column picker.
const PRICE_INDICATORS = ['rsi', 'macd', 'bbands', 'atr', 'vwap']

const INDICATORS = [
  { type: 'mid', name: 'Mid Price', desc: 'The fair price between the two sides of the book: (bid + ask) / 2. Add this first so indicators build on it.', params: [
    { key: 'col_bid', label: 'Bid column' }, { key: 'col_ask', label: 'Ask column' },
  ]},
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

const COLUMN_PARAM_KEYS = ['column', 'col_a', 'col_b', 'col_bid', 'col_ask']

const numericCols = (uploadData) =>
  uploadData.columns.filter((c) => c.detected_type !== 'timestamp').map((c) => c.name)

// Best-guess a column whose name matches one of the given fragments.
const guessCol = (cols, fragments) =>
  cols.find((c) => fragments.some((f) => c.toLowerCase().includes(f)))

const defaultForColumnKey = (key, cols) => {
  if (key === 'col_bid') return guessCol(cols, ['bid']) || cols[0]
  if (key === 'col_ask') return guessCol(cols, ['ask']) || cols[1] || cols[0]
  return guessCol(cols, ['close', 'mid', 'price']) || cols[0]
}

export default function Step2_FeatureEngineering({ uploadData, pipelineState, setPipelineState, preview }) {
  const [selected, setSelected] = useState('mid')
  const cols = numericCols(uploadData)
  const [params, setParams] = useState(() => ({
    col_bid: defaultForColumnKey('col_bid', cols),
    col_ask: defaultForColumnKey('col_ask', cols),
  }))

  const indicator = INDICATORS.find((i) => i.type === selected)
  const featuresAdded = preview?.features_added || []

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
      defaults[p.key] = COLUMN_PARAM_KEYS.includes(p.key)
        ? defaultForColumnKey(p.key, cols)
        : p.default
    })
    setParams(defaults)
  }

  return (
    <div className="step-panel">
      <h2>Feature Engineering</h2>
      <p className="step-desc">
        Add technical indicators and derived columns. New columns appear instantly in the live
        preview on the right.
      </p>

      <div className="info-banner">
        <strong>How the price is chosen.</strong> Market indicators (RSI, MACD, Bollinger Bands,
        ATR, VWAP) need a single price series. AlphaForge uses the <em>mid price</em> —
        <code>(bid + ask) / 2</code> — whenever it can, because using the bid or ask alone biases
        the result by half the spread. If your data has no mid column, add the{' '}
        <strong>Mid Price</strong> feature below first. Every feature you add shows exactly which
        column it was computed on.
      </div>

      <div className="feature-layout">
        <div className="feature-list">
          <h3>Added Features</h3>
          {(pipelineState.features || []).length === 0 && (
            <p className="muted">No features added yet</p>
          )}
          {(pipelineState.features || []).map((f, i) => {
            const info = featuresAdded[i]
            return (
              <div key={i} className="feature-item">
                <div className="feature-item-body">
                  <div className="feature-item-head">
                    <span className="mono feature-item-type">{f.type}</span>
                    <span className="muted">{JSON.stringify(f.params)}</span>
                  </div>
                  {info?.source && (
                    <div className="feature-source">
                      computed on <span className="mono">{info.source}</span>
                    </div>
                  )}
                  {info?.columns && (
                    <div className="feature-outcols">
                      → new column{info.columns.length > 1 ? 's' : ''}:{' '}
                      <span className="mono">{info.columns.join(', ')}</span>
                    </div>
                  )}
                </div>
                <button type="button" className="feature-remove" onClick={() => removeFeature(i)}>×</button>
              </div>
            )
          })}
        </div>

        <div className="add-feature-panel">
          <h3>Add Feature</h3>
          <select value={selected} onChange={(e) => onSelectIndicator(e.target.value)}>
            {INDICATORS.map((i) => (
              <option key={i.type} value={i.type}>{i.name}</option>
            ))}
          </select>

          {PRICE_INDICATORS.includes(selected) && (
            <p className="price-note">
              Runs on the auto-resolved <strong>mid price</strong>. No column to pick — the exact
              source is shown once you add it.
            </p>
          )}

          <div className="param-inputs">
            {indicator?.params.map((p) => (
              <label key={p.key}>
                {p.label || p.key}
                {COLUMN_PARAM_KEYS.includes(p.key) ? (
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
            className={`indicator-card ${selected === ind.type ? 'selected' : ''} ${ind.type === 'mid' ? 'indicator-card-mid' : ''}`}
            onClick={() => onSelectIndicator(ind.type)}
            onKeyDown={() => {}}
            role="button"
            tabIndex={0}
          >
            <strong>{ind.name}</strong>
            <p>{ind.desc}</p>
            <span className="hint mono">
              {PRICE_INDICATORS.includes(ind.type)
                ? 'source: mid price (auto)'
                : ind.params.map((p) => `${p.key}=${p.default ?? '…'}`).join(', ') || 'no params'}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
