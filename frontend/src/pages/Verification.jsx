import { useMemo, useState } from 'react'
import KpiCard from '../components/KpiCard'
import MetricComparisonChart from '../charts/MetricComparisonChart'
import { EmptyState, ErrorState } from '../components/States'
import { num } from '../services/constants'
import { useT } from '../i18n'

/* Verification page: does regime-aware post-processing actually add skill?
   Every number here is computed from the evaluation dataset by the backend
   (or, offline, from the browser demo sample). Nothing is hard-coded. */

// Metric names stay in their scientific form in every language; only the
// plain-language explanation is translated.
const ERROR_METRICS = [
  { key: 'rmse', label: 'RMSE', lowerIsBetter: true, unit: 'mm' },
  { key: 'mae', label: 'MAE', lowerIsBetter: true, unit: 'mm' },
]

const SKILL_METRICS = [
  { key: 'csi', label: 'CSI', lowerIsBetter: false },
  { key: 'pod', label: 'POD', lowerIsBetter: false },
  { key: 'far', label: 'FAR', lowerIsBetter: true },
  { key: 'ets', label: 'ETS', lowerIsBetter: false },
  { key: 'fss', label: 'FSS', lowerIsBetter: false },
]

export default function Verification({ verification, error, onRetry }) {
  const t = useT()
  const thresholds = verification?.thresholds_mm || []
  const [threshold, setThreshold] = useState(null)

  const active = threshold ?? (thresholds.length ? thresholds[0] : null)

  const { raw, ai } = useMemo(() => {
    if (!verification) return { raw: null, ai: null }
    const key = String(active)
    const rawBlock = verification.raw_nwp || {}
    const aiBlock = verification.ai_corrected || {}
    const rawThr = rawBlock.by_threshold?.[key] || {}
    const aiThr = aiBlock.by_threshold?.[key] || {}
    return {
      raw: { ...rawBlock, ...rawThr },
      ai: { ...aiBlock, ...aiThr },
    }
  }, [verification, active])

  if (error) {
    return (
      <ErrorState
        title="Verification report unavailable"
        message={error}
        onRetry={onRetry}
      />
    )
  }

  if (!verification) {
    return (
      <EmptyState
        title={t('technical.notAvailable')}
        message="Run python train_models.py in the backend folder to build the hold-out evaluation set, then reload this page."
      />
    )
  }

  if (verification.available === false) {
    return (
      <EmptyState
        title={t('technical.notAvailable')}
        message={
          verification.reason ||
          'Verification scores need matching observed rainfall, which is not available for this source.'
        }
      >
        {verification.source === 'live' ? (
          <p className="small dim" style={{ marginTop: 8, marginBottom: 0 }}>
            Switch to Demo / Test mode on the Data source page to see verification scores computed
            on the models' held-out evaluation period.
          </p>
        ) : null}
      </EmptyState>
    )
  }

  const imp = verification.improvement || {}
  const rows = [...ERROR_METRICS, ...SKILL_METRICS]

  const verdict = (metric) => {
    const r = raw?.[metric.key]
    const a = ai?.[metric.key]
    if (r === null || r === undefined || a === null || a === undefined) return { cls: '', text: 'n/a' }
    const better = metric.lowerIsBetter ? a < r : a > r
    const change = metric.lowerIsBetter ? ((r - a) / Math.abs(r)) * 100 : ((a - r) / Math.abs(r)) * 100
    return {
      cls: better ? 'better' : 'worse',
      text: `${change > 0 ? '+' : ''}${change.toFixed(1)}%`,
    }
  }

  return (
    <div className="grid page-enter">
      <div className="panel">
        <div className="panel-head">
          <h2>Why this page exists</h2>
          <span className="panel-note">
            {verification.sample_size} forecast/observation pairs
            {verification.period ? `, ${verification.period.start} to ${verification.period.end}` : ''}
          </span>
        </div>
        <p>
          The purpose of this comparison is to determine whether regime-aware post-processing
          improves forecast skill relative to the raw NWP forecast. Scores are computed on a
          hold-out period that the models never saw during training: the last stretch of days is
          withheld, so entire weather situations are unseen rather than individual rows.
        </p>
        <p className="small dim" style={{ marginBottom: 0 }}>
          Dataset: <span className="mono">{verification.dataset || 'demo'}</span>. A lower RMSE, MAE
          and FAR is better; a higher CSI, POD, ETS and FSS is better.
        </p>
      </div>

      <div className="grid kpis">
        <KpiCard label="RMSE, raw NWP" value={num(raw?.rmse, 2)} unit="mm" accent="#4d7a93" />
        <KpiCard
          label="RMSE, AI corrected"
          value={num(ai?.rmse, 2)}
          unit="mm"
          hint={imp.rmse_reduction_pct != null ? `${imp.rmse_reduction_pct}% lower error` : undefined}
          accent="#2fd4e8"
        />
        <KpiCard label="MAE, raw NWP" value={num(raw?.mae, 2)} unit="mm" accent="#4d7a93" />
        <KpiCard
          label="MAE, AI corrected"
          value={num(ai?.mae, 2)}
          unit="mm"
          hint={imp.mae_reduction_pct != null ? `${imp.mae_reduction_pct}% lower error` : undefined}
          accent="#2fd4e8"
        />
        <KpiCard
          label="Detection of heavy events"
          value={num(ai?.pod, 3)}
          hint={`POD, raw forecast ${num(raw?.pod, 3)}`}
          accent="#f2a63b"
        />
        <KpiCard
          label="Observed heavy events"
          value={raw?.observed_events ?? '-'}
          hint={`at or above ${active} mm`}
          accent="#8b6df2"
        />
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2>Event threshold</h2>
          <span className="panel-note">categorical scores are computed for each threshold</span>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {thresholds.map((t) => (
            <button
              key={t}
              className={`btn${Number(t) === Number(active) ? ' active' : ''}`}
              onClick={() => setThreshold(t)}
            >
              {t} mm
            </button>
          ))}
        </div>
      </div>

      <div className="grid two">
        <div className="panel">
          <div className="panel-head">
            <h2>Continuous error</h2>
            <span className="panel-note">lower is better</span>
          </div>
          <MetricComparisonChart raw={raw} ai={ai} metrics={ERROR_METRICS} />
        </div>
        <div className="panel">
          <div className="panel-head">
            <h2>Event skill at {active} mm</h2>
            <span className="panel-note">CSI, POD, ETS and FSS: higher is better. FAR: lower is better.</span>
          </div>
          <MetricComparisonChart raw={raw} ai={ai} metrics={SKILL_METRICS} />
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2>Verification report</h2>
          <span className="panel-note">raw NWP and AI corrected against observed rainfall</span>
        </div>
        <div className="table-wrap">
          <table className="metric-table">
            <thead>
              <tr>
                <th>Metric</th>
                <th className="num">Raw NWP</th>
                <th className="num">AI corrected</th>
                <th className="num">Change</th>
                <th>What it measures</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((metric) => {
                const v = verdict(metric)
                return (
                  <tr key={metric.key}>
                    <td>
                      {metric.label}
                      {metric.unit ? <span className="faint"> ({metric.unit})</span> : null}
                    </td>
                    <td className="num">{num(raw?.[metric.key], 3)}</td>
                    <td className="num">{num(ai?.[metric.key], 3)}</td>
                    <td className={`num ${v.cls}`}>{v.text}</td>
                    <td className="small dim">{t(`metrics.${metric.key}`)}</td>
                  </tr>
                )
              })}
              <tr>
                <td>Contingency counts</td>
                <td className="num">
                  {raw?.hits ?? '-'} / {raw?.misses ?? '-'} / {raw?.false_alarms ?? '-'}
                </td>
                <td className="num">
                  {ai?.hits ?? '-'} / {ai?.misses ?? '-'} / {ai?.false_alarms ?? '-'}
                </td>
                <td className="num faint">-</td>
                <td className="small dim">Hits / misses / false alarms at {active} mm.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {verification.notes?.length ? (
        <div className="panel">
          <div className="panel-head">
            <h2>How to read these numbers</h2>
          </div>
          <ul className="tight small dim">
            {verification.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}
