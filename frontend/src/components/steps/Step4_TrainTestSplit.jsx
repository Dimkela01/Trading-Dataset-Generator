import './Steps.css'

export default function Step4_TrainTestSplit({ uploadData, pipelineState, setPipelineState }) {
  const split = pipelineState.split || { method: 'temporal', params: { train_ratio: 0.8 } }
  const method = split.method || 'temporal'
  const params = split.params || {}
  const total = uploadData.row_count
  const trainRatio = params.train_ratio ?? 0.8
  const trainRows = Math.floor(total * trainRatio)
  const testRows = total - trainRows

  // Mirror the backend embargo: labels look forward, so boundary rows are purged
  // to stop training labels peeking into the test period.
  const label = pipelineState.label
  const embargo = !label
    ? 0
    : label.method === 'forward_return'
      ? label.params?.periods ?? 5
      : label.method === 'triple_barrier'
        ? label.params?.max_periods ?? 10
        : 0

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

      <div className="explain">
        <p>
          <strong>What is this step?</strong> You&apos;re choosing which rows the model{' '}
          <em>learns from</em> (train) and which are held back to check whether it actually works on
          data it has never seen (test).
        </p>
        <p>
          Because this is time-series data, AlphaForge <strong>never shuffles</strong> — the test
          set is always your most recent rows, exactly like predicting the future from the past.
        </p>
      </div>

      <div className="method-cards">
        <button
          type="button"
          className={`method-card ${method === 'temporal' ? 'selected' : ''}`}
          onClick={() => setMethod('temporal')}
        >
          <strong>TEMPORAL SPLIT<span className="rec-badge">recommended</span></strong>
          <p>One cut point: earlier rows train, later rows test</p>
        </button>
        <button
          type="button"
          className={`method-card ${method === 'walk_forward' ? 'selected' : ''}`}
          onClick={() => setMethod('walk_forward')}
        >
          <strong>WALK-FORWARD</strong>
          <p>Repeat over several periods to check robustness (advanced)</p>
        </button>
      </div>

      <div className="choice-help">
        {method === 'temporal' ? (
          <>
            <strong>Temporal split</strong> picks a single point in time. Everything before it
            trains the model; everything after tests it. Simple and the right choice for most
            datasets — <strong>80% train</strong> is a solid starting point.
          </>
        ) : (
          <>
            <strong>Walk-forward</strong> repeats the train/test process over several expanding
            windows, so you can confirm the model holds up across different market periods rather
            than getting lucky on one. Use it when you specifically need cross-validation. The export
            file contains the last (largest) fold.
          </>
        )}
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

          {embargo > 0 && (
            <div className="embargo-note">
              <strong>🛡 Leakage guard:</strong> your labels look {embargo} bars into the future, so
              AlphaForge automatically removes the {embargo} rows at the train/test boundary. This
              stops the model from &ldquo;seeing&rdquo; test-period prices during training — a
              common, hard-to-spot mistake that makes results look better than they really are.
            </div>
          )}
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
