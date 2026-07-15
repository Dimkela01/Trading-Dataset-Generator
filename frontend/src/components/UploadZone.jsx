import { useCallback, useState } from 'react'
import './UploadZone.css'

const LOG_LINES = [
  'Reading file...',
  'Detecting columns...',
  'Analyzing granularity...',
  'Checking for gaps...',
]

const FEATURE_PILLS = [
  { icon: '⟳', text: 'Automated Feature Engineering' },
  { icon: '◈', text: 'Order Book–Aware Labels' },
  { icon: '⟁', text: 'Walk-Forward Split' },
]

function DataIcon() {
  return (
    <svg className="upload-data-icon" viewBox="0 0 40 40" width="40" height="40" aria-hidden>
      <line x1="6" y1="10" x2="34" y2="10" stroke="#f0b429" strokeWidth="2" />
      <line x1="6" y1="18" x2="34" y2="18" stroke="#f0b429" strokeWidth="2" opacity="0.7" />
      <line x1="6" y1="26" x2="34" y2="26" stroke="#f0b429" strokeWidth="2" opacity="0.5" />
      <line x1="6" y1="34" x2="28" y2="34" stroke="#f0b429" strokeWidth="2" opacity="0.35" />
    </svg>
  )
}

export default function UploadZone({ onUpload, loading, error }) {
  const [dragOver, setDragOver] = useState(false)
  const [visibleLogs, setVisibleLogs] = useState([])

  const processFile = useCallback(
    async (file) => {
      if (!file) return
      setVisibleLogs([])
      for (let i = 0; i < LOG_LINES.length; i++) {
        await new Promise((r) => setTimeout(r, 400))
        setVisibleLogs((prev) => [...prev, LOG_LINES[i]])
      }
      await onUpload(file)
    },
    [onUpload],
  )

  const onDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    processFile(file)
  }

  return (
    <div className="upload-screen upload-screen-grid">
      <div className="upload-hero">
        <h1 className="hero-title mono">ALPHAFORGE</h1>
        <p className="hero-tagline">From raw market data to model-ready datasets.</p>
        <p className="hero-sub">No boilerplate. No temporal leakage. No guesswork.</p>
        <p className="hero-intro">
          Upload your raw trading dataset and let the guided pipeline walk you through transforming
          it, step by step, into a clean, machine-learning-ready training set.
        </p>
      </div>

      <div
        className={`upload-zone march-border ${dragOver ? 'drag-over' : ''} ${loading ? 'loading' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
      >
        <DataIcon />
        <p className="upload-title">DROP YOUR DATASET</p>
        <p className="upload-sub">
          CSV or Parquet • OHLCV, tick data, custom features — anything with a timestamp
        </p>
        <label className="file-btn mono">
          $ open file<span className="cursor-underscore">_</span>
          <input
            type="file"
            accept=".csv,.parquet,.pq,.txt"
            hidden
            disabled={loading}
            onChange={(e) => processFile(e.target.files[0])}
          />
        </label>
      </div>

      {error && (
        <div className="upload-error mono" role="alert">
          <span className="upload-error-icon">✕</span> Couldn&apos;t read that file: {error}
          <span className="upload-error-hint">Try a CSV or Parquet file with a timestamp column.</span>
        </div>
      )}

      <div className="feature-pills">
        {FEATURE_PILLS.map((p) => (
          <div key={p.text} className="feature-pill mono">
            <span className="pill-icon">{p.icon}</span> {p.text}
          </div>
        ))}
      </div>

      {(loading || visibleLogs.length > 0) && (
        <div className="terminal-log mono">
          {visibleLogs.map((line, i) => (
            <div key={i} className="log-line">
              <span className="log-prompt">&gt;</span> {line}
            </div>
          ))}
          {loading && <div className="log-line cursor-blink">_</div>}
        </div>
      )}
    </div>
  )
}
