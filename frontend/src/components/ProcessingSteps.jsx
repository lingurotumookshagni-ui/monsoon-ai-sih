import { useT } from '../i18n'

/* Progress view of the backend pipeline.

   The step list mirrors the stages the API actually reports back from
   POST /api/process, including the real time each stage took. While a run is
   in flight the steps advance one by one; when the response arrives the list
   is replaced by the backend's own stage report. Nothing is faked: if a stage
   fails, it is shown as failed. */

const STEP_KEYS = [
  'load',
  'regime',
  'postprocess',
  'probability',
  'metrics',
  'results',
  'visualisation',
]

export default function ProcessingSteps({ running, activeIndex = 0, stages = null }) {
  const t = useT()
  const report = stages && stages.length ? stages : null
  const keys = report ? report.map((s) => s.key) : STEP_KEYS
  const done = report ? report.length : activeIndex
  const progress = Math.round((done / STEP_KEYS.length) * 100)

  const statusOf = (index, key) => {
    if (report) {
      const stage = report.find((s) => s.key === key)
      return stage?.status === 'failed' ? 'failed' : 'done'
    }
    if (!running) return 'idle'
    if (index < activeIndex) return 'done'
    if (index === activeIndex) return 'active'
    return 'idle'
  }

  return (
    <div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${report ? 100 : progress}%` }} />
      </div>
      <div className="steps">
        {keys.map((key, i) => {
          const status = statusOf(i, key)
          const stage = report?.find((s) => s.key === key)
          return (
            <div className={`step ${status}`} key={key}>
              <span className="step-mark" aria-hidden="true">
                {status === 'done' ? '✓' : status === 'failed' ? '×' : status === 'active' ? '' : i + 1}
              </span>
              <span className="step-label">{t(`process.step.${key}`)}</span>
              {stage ? <span className="step-meta">{stage.ms} ms</span> : null}
            </div>
          )
        })}
      </div>
    </div>
  )
}
