import { useCallback, useEffect, useState } from 'react'
import { uploadFile, previewPipeline, selectAsset } from './api/client'
import UploadZone from './components/UploadZone'
import AssetSelect from './components/AssetSelect'
import DataSummary from './components/DataSummary'
import WizardShell from './components/WizardShell'

function buildInitialPipeline(sessionId, uploadData) {
  const tsCol = uploadData.timestamp_column
  const column_transforms = uploadData.columns
    .filter((c) => c.name !== tsCol)
    .map((c) => ({ column: c.name, transform: 'none', params: {} }))

  return {
    session_id: sessionId,
    column_transforms,
    features: [],
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
    split: { method: 'temporal', params: { train_ratio: 0.8 } },
  }
}

export default function App() {
  const [screen, setScreen] = useState('upload')
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [uploadData, setUploadData] = useState(null)
  const [pipelineState, setPipelineState] = useState(null)
  const [wizardStep, setWizardStep] = useState(1)
  const [preview, setPreview] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState(null)

  const applyUploadResult = useCallback((data) => {
    setSessionId(data.session_id)
    setUploadData(data)
    setPipelineState(buildInitialPipeline(data.session_id, data))
    if (data.is_multi_asset) {
      setScreen('assetSelect')
    } else {
      setScreen('summary')
    }
  }, [])

  const handleUpload = useCallback(
    async (file) => {
      setLoading(true)
      try {
        const data = await uploadFile(file)
        applyUploadResult(data)
      } catch (e) {
        alert(e.message)
      } finally {
        setLoading(false)
      }
    },
    [applyUploadResult],
  )

  const handleAssetSelect = useCallback(
    async (symbolValue) => {
      setLoading(true)
      try {
        const data = await selectAsset(sessionId, uploadData.symbol_column, symbolValue)
        applyUploadResult({ ...data, is_multi_asset: false })
        setScreen('summary')
      } catch (e) {
        alert(e.message)
      } finally {
        setLoading(false)
      }
    },
    [sessionId, uploadData, applyUploadResult],
  )

  useEffect(() => {
    if (screen !== 'wizard' || !pipelineState) return

    // The label is only relevant from the Labels step onward; showing it on
    // Columns/Features would surface a label the user hasn't configured yet.
    const withLabel = wizardStep >= 3

    const timer = setTimeout(async () => {
      setPreviewLoading(true)
      setPreviewError(null)
      try {
        const result = await previewPipeline(pipelineState, withLabel)
        setPreview(result)
      } catch (e) {
        setPreviewError(e.message)
      } finally {
        setPreviewLoading(false)
      }
    }, 500)

    return () => clearTimeout(timer)
  }, [pipelineState, screen, wizardStep])

  return (
    <>
      <header className="app-header">
        <h1>ALPHAFORGE</h1>
        <span>trading dataset preparation</span>
      </header>

      {screen === 'upload' && <UploadZone onUpload={handleUpload} loading={loading} />}

      {screen === 'assetSelect' && uploadData && (
        <AssetSelect
          data={uploadData}
          onSelect={handleAssetSelect}
          onBackToUpload={() => {
            setScreen('upload')
            setUploadData(null)
            setSessionId(null)
          }}
        />
      )}

      {screen === 'summary' && uploadData && (
        <DataSummary data={uploadData} onBegin={() => setScreen('wizard')} />
      )}

      {screen === 'wizard' && uploadData && pipelineState && (
        <WizardShell
          step={wizardStep}
          setStep={setWizardStep}
          uploadData={uploadData}
          pipelineState={pipelineState}
          setPipelineState={setPipelineState}
          preview={preview}
          previewLoading={previewLoading}
          previewError={previewError}
          sessionId={sessionId}
        />
      )}
    </>
  )
}
