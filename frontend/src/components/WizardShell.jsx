import LivePreview from './LivePreview'
import Step1_ColumnManager from './steps/Step1_ColumnManager'
import Step2_FeatureEngineering from './steps/Step2_FeatureEngineering'
import Step3_LabelGeneration from './steps/Step3_LabelGeneration'
import Step4_TrainTestSplit from './steps/Step4_TrainTestSplit'
import ExportButton from './ExportButton'
import './WizardShell.css'

const STEPS = [
  { id: 1, label: 'Columns' },
  { id: 2, label: 'Features' },
  { id: 3, label: 'Labels' },
  { id: 4, label: 'Split' },
]

export default function WizardShell({
  step,
  setStep,
  uploadData,
  pipelineState,
  setPipelineState,
  preview,
  previewLoading,
  previewError,
  sessionId,
}) {
  const renderStep = () => {
    const props = { uploadData, pipelineState, setPipelineState }
    switch (step) {
      case 1:
        return <Step1_ColumnManager {...props} />
      case 2:
        return <Step2_FeatureEngineering {...props} preview={preview} />
      case 3:
        return <Step3_LabelGeneration {...props} preview={preview} />
      case 4:
        return <Step4_TrainTestSplit {...props} />
      default:
        return null
    }
  }

  return (
    <div className="wizard-layout">
      <div className="wizard-main">
        <div className="step-indicator">
          {STEPS.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`step-item ${step === s.id ? 'active' : ''} ${step > s.id ? 'done' : ''}`}
              onClick={() => setStep(s.id)}
            >
              <span className="step-num">{step > s.id ? '✓' : s.id}</span>
              <span className="step-label">{s.label}</span>
            </button>
          ))}
        </div>

        <div className="step-content">{renderStep()}</div>

        <div className="step-nav">
          {step > 1 && (
            <button type="button" onClick={() => setStep(step - 1)}>
              ← Back
            </button>
          )}
          {step < 4 && (
            <button type="button" className="primary" onClick={() => setStep(step + 1)}>
              Next →
            </button>
          )}
        </div>

        {step === 4 && (
          <ExportButton pipelineState={{ ...pipelineState, session_id: sessionId }} />
        )}
      </div>

      <div className="wizard-preview">
        <LivePreview preview={preview} loading={previewLoading} error={previewError} />
      </div>
    </div>
  )
}
