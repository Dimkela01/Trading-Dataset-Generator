import { useState } from 'react'
import './AssetSelect.css'

export default function AssetSelect({ data, onSelect, onBackToUpload }) {
  const [selected, setSelected] = useState(null)
  const counts = data.symbol_row_counts || {}
  const symbols = data.symbols || []

  return (
    <div className="asset-select-screen">
      <h2 className="asset-warning mono">MULTI-ASSET DATASET DETECTED</h2>
      <p className="asset-sub">
        This dataset contains <strong>{symbols.length}</strong> assets in a single file.
        AlphaForge processes one asset at a time to ensure temporal integrity of features and labels.
      </p>

      <div className="asset-grid">
        {symbols.map((sym) => (
          <button
            key={sym}
            type="button"
            className={`asset-chip mono ${selected === sym ? 'selected' : ''}`}
            onClick={() => setSelected(sym)}
          >
            <span className="chip-symbol">{sym}</span>
            <span className="chip-rows">{(counts[sym] || 0).toLocaleString()} rows</span>
          </button>
        ))}
      </div>

      <div className="asset-actions">
        <button
          type="button"
          className="primary"
          disabled={!selected}
          onClick={() => onSelect(selected)}
        >
          SELECT ASSET TO CONTINUE →
        </button>
        <button type="button" className="secondary-link" onClick={onBackToUpload}>
          I'll upload a single-asset file instead
        </button>
      </div>
    </div>
  )
}
