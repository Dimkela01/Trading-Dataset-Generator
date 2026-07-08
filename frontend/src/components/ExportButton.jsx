import { useState } from 'react'
import { exportDataset } from '../api/client'
import './ExportButton.css'

const PROGRESS_STEPS = [
  'Applying transforms...',
  'Computing features...',
  'Generating labels...',
  'Splitting dataset...',
  'Building report...',
  'Packaging export...',
]

export default function ExportButton({ pipelineState }) {
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)
  const [logs, setLogs] = useState([])
  const [error, setError] = useState(null)

  const handleExport = async () => {
    setLoading(true)
    setDone(false)
    setError(null)
    setLogs([])

    try {
      for (let i = 0; i < PROGRESS_STEPS.length; i++) {
        await new Promise((r) => setTimeout(r, 500))
        setLogs((prev) => [...prev, PROGRESS_STEPS[i]])
      }

      const blob = await exportDataset(pipelineState)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'alphaforge_export.zip'
      a.click()
      URL.revokeObjectURL(url)
      setDone(true)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="export-section">
      <button
        type="button"
        className={`export-btn primary ${loading ? 'loading' : ''} ${done ? 'done' : ''}`}
        onClick={handleExport}
        disabled={loading}
      >
        {loading ? 'GENERATING...' : done ? 'DOWNLOAD READY ↓' : 'GENERATE DATASET'}
      </button>

      {(loading || logs.length > 0) && (
        <div className="export-log mono">
          {logs.map((line, i) => (
            <div key={i}>&gt; {line}</div>
          ))}
        </div>
      )}

      {error && <p className="export-error">{error}</p>}
      {done && !error && (
        <p className="export-success">Export complete. Check your downloads folder.</p>
      )}
    </div>
  )
}
