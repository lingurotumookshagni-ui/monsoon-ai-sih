import { useState } from 'react'
import ProcessingSteps from '../components/ProcessingSteps'
import RawVsCorrectedChart from '../charts/RawVsCorrectedChart'
import { ErrorState } from '../components/States'
import { api } from '../services/api'
import { useT } from '../i18n'
import { mm, num, regimeLabel } from '../services/constants'

/* Post-processing page: the pipeline as a visual workflow, a button that runs
   it for real on the backend, and the raw-vs-corrected comparison it produced. */
export default function PostProcessing({ rows, source, backendOnline, verification, onToast }) {
  const t = useT()
  const [running, setRunning] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const [report, setReport] = useState(null)
  const [error, setError] = useState(null)

  const flow = [
    { key: 'raw', title: 'Raw NWP forecast', desc: 'The rainfall amount the numerical model produced, before any correction.' },
    { key: 'regime', title: t('field.regime'), desc: 'A random forest classifies the weather situation for each district.' },
    { key: 'correct', title: t('field.correctedForecast'), desc: 'The regime selects a correction model trained only on that situation; it predicts the forecast error and adds it back.' },
    { key: 'probability', title: t('field.heavyProbability'), desc: 'Calibrated classifiers estimate the chance of crossing the heavy and very heavy thresholds.' },
    { key: 'district', title: t('nav.allDistricts'), desc: 'Results are assembled into the district-level product shown across this dashboard.' },
    { key: 'verify', title: t('nav.metrics'), desc: 'Raw and corrected forecasts are scored against observations on a held-out period.' },
  ]

  const run = async () => {
    if (!backendOnline) {
      setError(t('error.connect'))
      return
    }
    setRunning(true)
    setError(null)
    setReport(null)
    setActiveIndex(0)
    // Advance the visible step while the request is in flight; the backend's
    // own stage report replaces this as soon as it arrives.
    const ticker = setInterval(() => setActiveIndex((i) => Math.min(i + 1, 6)), 320)
    try {
      const res = await api.process({ source })
      setReport(res)
      if (onToast) onToast(t('toast.processingDone'))
    } catch (err) {
      setError(err.message || t('error.generic'))
    } finally {
      clearInterval(ticker)
      setRunning(false)
    }
  }

  const regimeCounts = report?.stages?.find((s) => s.key === 'regime')?.detail?.counts

  return (
    <div className="grid page-enter">
      <div className="panel">
        <div className="panel-head">
          <h2>{t('process.title')}</h2>
          <button className="btn primary" onClick={run} disabled={running}>
            {running ? t('process.running') : t('process.run')}
          </button>
        </div>

        {running || report ? (
          <div style={{ marginBottom: 14 }}>
            <ProcessingSteps
              running={running}
              activeIndex={activeIndex}
              stages={report?.stages || null}
            />
            {report ? (
              <div className="small dim" style={{ marginTop: 8 }}>
                {t('process.complete')} - {report.total_ms} ms, {report.engine_mode}
                {report.demo_mode ? `, ${t('app.demoData')}` : ''}
              </div>
            ) : null}
          </div>
        ) : null}

        {error ? <ErrorState title={t('common.backendOffline')} message={error} onRetry={run} /> : null}

        <div className="flow stagger">
          {flow.map((step, i) => (
            <div key={step.key}>
              <div className="flow-step">
                <span className="flow-index">{i + 1}</span>
                <div>
                  <strong>{step.title}</strong>
                  <div className="small dim">{step.desc}</div>
                </div>
              </div>
              {i < flow.length - 1 ? <div className="flow-arrow" aria-hidden="true">↓</div> : null}
            </div>
          ))}
        </div>
      </div>

      {regimeCounts ? (
        <div className="panel">
          <div className="panel-head">
            <h2>{t('field.regime')}</h2>
            <span className="panel-note">districts classified in the last run</span>
          </div>
          <div className="result-grid">
            {Object.entries(regimeCounts).map(([regime, count]) => (
              <div className="result-item" key={regime}>
                <div className="label">{t(`regime.${regime}`) || regimeLabel(regime)}</div>
                <div className="value">{count}</div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="panel">
        <div className="panel-head">
          <h2>{t('process.rawVsCorrected')}</h2>
          <span className="panel-note">
            {rows.length} {t('common.districts').toLowerCase()}
          </span>
        </div>
        <RawVsCorrectedChart rows={rows} />
        <div className="small dim" style={{ marginTop: 8 }}>
          {t('field.rawForecast')}: {mm(average(rows, 'raw_nwp_mm'))} mm ·{' '}
          {t('field.correctedForecast')}: {mm(average(rows, 'corrected_mm'))} mm
          {verification?.ai_corrected?.rmse != null
            ? ` · RMSE ${num(verification.raw_nwp?.rmse, 2)} → ${num(verification.ai_corrected?.rmse, 2)}`
            : ''}
        </div>
      </div>
    </div>
  )
}

function average(rows, key) {
  if (!rows.length) return 0
  return rows.reduce((a, b) => a + (Number(b[key]) || 0), 0) / rows.length
}
