import './Steps.css'

export default function Step4_TrainTestSplit({ uploadData, pipelineState, setPipelineState }) {
  const split = pipelineState.split || { method: 'temporal', params: { train_ratio: 0.8 } }
  const method = split.method || 'temporal'
  const params = split.params || {}
  const total = uploadData.row_count
  const trainRatio = params.train_ratio ?? 0.8
  const trainRows = Math.floor(total * trainRatio)
  const testRows = total - trainRows

  const setMethod = (m) => {
    const defaults = m === 'walk_forward'
      ? { n_splits: 5, gap: 0 }
      : { train_ratio: 0.8 }
    setPipelineState((s) => ({ ...s, split: { method: m, params: defaults } }))
  }

  const setParam = (key, value) => {
    setPipelineState((s) => ({
      ...s,
      split: { ...s.split, params: { ...s.split.params, [key]: value } },
    }))
  }

  return (
    <div className="step-panel">
      <h2>Train / Test Split</h2>

      <div className="warning-banner">
        ⚠ AlphaForge never shuffles time series data. Temporal ordering is always preserved.
      </div>

      <div className="method-cards">
        <button
          type="button"
          className={`method-card ${method === 'temporal' ? 'selected' : ''}`}
          onClick={() => setMethod('temporal')}
        >
          <strong>TEMPORAL SPLIT</strong>
          <p>Single chronological train/test split</p>
        </button>
        <button
          type="button"
          className={`method-card ${method === 'walk_forward' ? 'selected' : ''}`}
          onClick={() => setMethod('walk_forward')}
        >
          <strong>WALK-FORWARD</strong>
          <p>Expanding window cross-validation (export uses last fold)</p>
        </button>
      </div>

      {method === 'temporal' && (
        <div className="split-controls">
          <label>
            Train ratio: {(trainRatio * 100).toFixed(0)}%
            <input
              type="range"
              min="0.5"
              max="0.95"
              step="0.01"
              value={trainRatio}
              onChange={(e) => setParam('train_ratio', parseFloat(e.target.value))}
            />
          </label>

          <div className="timeline-viz">
            <div className="timeline-bar">
              <div className="timeline-train" style={{ width: `${trainRatio * 100}%` }} />
              <div className="timeline-test" style={{ width: `${(1 - trainRatio) * 100}%` }} />
            </div>
            <div className="timeline-labels">
              <span>Train: {trainRows.toLocaleString()} rows</span>
              <span>Test: {testRows.toLocaleString()} rows</span>
            </div>
          </div>
        </div>
      )}

      {method === 'walk_forward' && (
        <div className="split-controls">
          <label>
            N splits
            <input
              type="number"
              min={2}
              max={20}
              value={params.n_splits ?? 5}
              onChange={(e) => setParam('n_splits', parseInt(e.target.value, 10))}
            />
          </label>
          <label>
            Gap (rows)
            <input
              type="number"
              min={0}
              value={params.gap ?? 0}
              onChange={(e) => setParam('gap', parseInt(e.target.value, 10))}
            />
          </label>

          <svg className="wf-diagram" viewBox="0 0 300 100" width="300" height="100">
            <rect x="10" y="60" width="80" height="20" fill="#3b82f6" opacity="0.8"/>
            <rect x="95" y="60" width="30" height="20" fill="#f0b429" opacity="0.6"/>
            <rect x="10" y="35" width="120" height="20" fill="#3b82f6" opacity="0.8"/>
            <rect x="135" y="35" width="30" height="20" fill="#f0b429" opacity="0.6"/>
            <rect x="10" y="10" width="160" height="20" fill="#3b82f6" opacity="0.8"/>
            <rect x="175" y="10" width="30" height="20" fill="#f0b429" opacity="0.6"/>
            <text x="10" y="95" fill="#6b6b8a" fontSize="9">Expanding train window →</text>
          </svg>
        </div>
      )}
    </div>
  )
}
