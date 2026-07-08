import { useEffect } from 'react'
import './Steps.css'

const METHODS = [
  { id: 'forward_return', title: 'FORWARD RETURN', desc: 'Mid-price or execution-aware forward labels' },
  { id: 'triple_barrier', title: 'TRIPLE BARRIER', desc: 'TP / SL / time barrier labels' },
  { id: 'custom', title: 'CUSTOM EXPRESSION', desc: 'Pandas eval expression' },
]

function MidPriceDiagram() {
  return (
    <svg className="label-diagram" viewBox="0 0 220 90" width="220" height="90">
      <polyline points="10,60 50,45 90,50 130,35 170,40" fill="none" stroke="#6b6b8a" strokeWidth="2" />
      <line x1="10" y1="30" x2="200" y2="30" stroke="#4ade80" strokeDasharray="4" opacity="0.8" />
      <line x1="10" y1="70" x2="200" y2="70" stroke="#f87171" strokeDasharray="4" opacity="0.8" />
      <rect x="10" y="30" width="190" height="40" fill="#f0b429" opacity="0.08" />
      <text x="100" y="52" fill="#6b6b8a" fontSize="10" textAnchor="middle">HOLD</text>
      <text x="12" y="26" fill="#4ade80" fontSize="9">+threshold</text>
      <text x="12" y="82" fill="#f87171" fontSize="9">-threshold</text>
    </svg>
  )
}

function ExecutionDiagram() {
  return (
    <svg className="label-diagram" viewBox="0 0 220 100" width="220" height="100">
      <polyline points="10,55 60,50 110,58 160,42" fill="none" stroke="#6b6b8a" strokeWidth="2" />
      <circle cx="60" cy="50" r="4" fill="#f87171" />
      <text x="68" y="48" fill="#f87171" fontSize="9">ASK entry</text>
      <circle cx="160" cy="42" r="4" fill="#4ade80" />
      <text x="120" y="38" fill="#4ade80" fontSize="9">BID exit</text>
      <line x1="60" y1="50" x2="160" y2="42" stroke="#f0b429" strokeWidth="1" strokeDasharray="3" />
      <text x="95" y="65" fill="#f0b429" fontSize="9">spread</text>
    </svg>
  )
}

function TripleBarrierDiagram({ realistic }) {
  if (realistic) {
    return (
      <p className="hint diagram-caption">
        Entry at ask[t], TP/SL checked against bid[t+1..t+N]
      </p>
    )
  }
  return (
    <svg className="label-diagram" viewBox="0 0 200 80" width="200" height="80">
      <line x1="10" y1="20" x2="190" y2="20" stroke="#4ade80" strokeDasharray="4" />
      <text x="10" y="15" fill="#4ade80" fontSize="9">TP</text>
      <polyline points="10,50 60,45 110,55 160,40" fill="none" stroke="#6b6b8a" strokeWidth="2" />
      <line x1="10" y1="65" x2="190" y2="65" stroke="#f87171" strokeDasharray="4" />
      <text x="10" y="75" fill="#f87171" fontSize="9">SL</text>
      <line x1="170" y1="10" x2="170" y2="70" stroke="#f0b429" strokeDasharray="2" />
      <text x="175" y="40" fill="#f0b429" fontSize="9">Time</text>
    </svg>
  )
}

export default function Step3_LabelGeneration({ uploadData, pipelineState, setPipelineState }) {
  const hasOrderBook = uploadData?.has_order_book === true
  const label = pipelineState.label || { method: 'forward_return', params: {} }
  const method = label.method || 'forward_return'
  const params = label.params || {}

  useEffect(() => {
    if (!pipelineState.label) {
      setPipelineState((s) => ({
        ...s,
        label: {
          method: 'forward_return',
          params: {
            periods: 5,
            mode: 'classification',
            framing: 'mid_price_direction',
            up_threshold: 0.005,
            down_threshold: -0.005,
          },
        },
      }))
    }
  }, [pipelineState.label, setPipelineState])

  const setMethod = (m) => {
    const defaults = {
      forward_return: {
        periods: 5,
        mode: 'classification',
        framing: 'mid_price_direction',
        up_threshold: 0.005,
        down_threshold: -0.005,
      },
      triple_barrier: { tp: 0.02, sl: 0.02, max_periods: 10, barrier_mode: 'simple' },
      custom: { expression: 'close.shift(-5) > close * 1.02' },
    }
    setPipelineState((s) => ({ ...s, label: { method: m, params: defaults[m] } }))
  }

  const setParam = (key, value) => {
    setPipelineState((s) => ({
      ...s,
      label: { ...s.label, params: { ...s.label.params, [key]: value } },
    }))
  }

  const setParams = (updates) => {
    setPipelineState((s) => ({
      ...s,
      label: { ...s.label, params: { ...s.label.params, ...updates } },
    }))
  }

  const mode = params.mode || 'classification'
  const framing = params.framing || 'mid_price_direction'
  const barrierMode = params.barrier_mode || 'simple'

  return (
    <div className="step-panel">
      <h2>Label Generation</h2>

      <div className="method-cards">
        {METHODS.map((m) => (
          <button
            key={m.id}
            type="button"
            className={`method-card ${method === m.id ? 'selected' : ''}`}
            onClick={() => setMethod(m.id)}
          >
            <strong>{m.title}</strong>
            <p>{m.desc}</p>
          </button>
        ))}
      </div>

      <div className="label-form">
        {method === 'forward_return' && (
          <>
            <label>
              Lookahead periods (T)
              <input
                type="number"
                min={1}
                value={params.periods ?? 5}
                onChange={(e) => setParam('periods', parseInt(e.target.value, 10))}
              />
              <span className="hint">Bars forward for label calculation</span>
            </label>
            <label>
              Output type
              <select value={mode} onChange={(e) => setParam('mode', e.target.value)}>
                <option value="regression">Regression</option>
                <option value="classification">Classification</option>
              </select>
            </label>

            {mode === 'regression' && (
              <p className="hint">
                Label = (mid[t+T] − mid[t]) / mid[t]. Uses bid/ask mid when available, else close.
              </p>
            )}

            {mode === 'classification' && (
              <>
                <div className="segmented-control">
                  <button
                    type="button"
                    className={framing === 'mid_price_direction' ? 'active' : ''}
                    onClick={() => setParams({ framing: 'mid_price_direction' })}
                  >
                    MID PRICE DIRECTION
                  </button>
                  <button
                    type="button"
                    className={framing === 'execution_aware' ? 'active' : ''}
                    disabled={!hasOrderBook}
                    title={
                      hasOrderBook
                        ? 'Entry/exit at bid-ask'
                        : 'Requires best_bid and best_ask columns'
                    }
                    onClick={() =>
                      hasOrderBook &&
                      setParams({
                        framing: 'execution_aware',
                        direction: params.direction || 'long',
                        min_profit_threshold: params.min_profit_threshold ?? 0.001,
                      })
                    }
                  >
                    EXECUTION-AWARE
                  </button>
                </div>

                {!hasOrderBook && (
                  <p className="warn-hint">
                    Execution-aware framing requires best_bid and best_ask columns in your dataset.
                  </p>
                )}

                {framing === 'mid_price_direction' && (
                  <>
                    <MidPriceDiagram />
                    <label>
                      Up threshold
                      <input
                        type="number"
                        step="0.001"
                        value={params.up_threshold ?? 0.005}
                        onChange={(e) => setParam('up_threshold', parseFloat(e.target.value))}
                      />
                      <span className="hint">Label +1 if mid return exceeds this</span>
                    </label>
                    <label>
                      Down threshold
                      <input
                        type="number"
                        step="0.001"
                        value={params.down_threshold ?? -0.005}
                        onChange={(e) => setParam('down_threshold', parseFloat(e.target.value))}
                      />
                      <span className="hint">Label −1 if mid return below this</span>
                    </label>
                  </>
                )}

                {framing === 'execution_aware' && hasOrderBook && (
                  <>
                    <ExecutionDiagram />
                    <label>
                      Direction
                      <select
                        value={params.direction ?? 'long'}
                        onChange={(e) => setParam('direction', e.target.value)}
                      >
                        <option value="long">Long</option>
                        <option value="short">Short</option>
                        <option value="both">Both (label_long + label_short)</option>
                      </select>
                    </label>
                    <label>
                      Min profit threshold
                      <input
                        type="number"
                        step="0.0001"
                        value={params.min_profit_threshold ?? 0.001}
                        onChange={(e) => setParam('min_profit_threshold', parseFloat(e.target.value))}
                      />
                      <span className="hint">Minimum return after spread to label as profitable</span>
                    </label>
                  </>
                )}
              </>
            )}
          </>
        )}

        {method === 'triple_barrier' && (
          <>
            <div className="segmented-control">
              <button
                type="button"
                className={barrierMode === 'simple' ? 'active' : ''}
                onClick={() => setParam('barrier_mode', 'simple')}
              >
                SIMPLE
              </button>
              <button
                type="button"
                className={barrierMode === 'realistic' ? 'active' : ''}
                disabled={!hasOrderBook}
                title={
                  hasOrderBook
                    ? 'Order book aware barriers'
                    : 'Requires best_bid and best_ask columns'
                }
                onClick={() => hasOrderBook && setParam('barrier_mode', 'realistic')}
              >
                REALISTIC
              </button>
            </div>
            {!hasOrderBook && (
              <p className="warn-hint">Realistic mode requires best_bid and best_ask columns.</p>
            )}
            <TripleBarrierDiagram realistic={barrierMode === 'realistic' && hasOrderBook} />
            <label>
              Take profit %
              <input type="number" step="0.01" value={params.tp ?? 0.02} onChange={(e) => setParam('tp', parseFloat(e.target.value))} />
            </label>
            <label>
              Stop loss %
              <input type="number" step="0.01" value={params.sl ?? 0.02} onChange={(e) => setParam('sl', parseFloat(e.target.value))} />
            </label>
            <label>
              Max periods
              <input type="number" value={params.max_periods ?? 10} onChange={(e) => setParam('max_periods', parseInt(e.target.value, 10))} />
            </label>
          </>
        )}

        {method === 'custom' && (
          <label>
            Expression
            <textarea
              className="expr-input mono"
              rows={4}
              value={params.expression ?? ''}
              onChange={(e) => setParam('expression', e.target.value)}
              placeholder="close.shift(-5) > close * 1.02"
            />
            <span className="hint">We'll validate this expression on export</span>
          </label>
        )}
      </div>
    </div>
  )
}
