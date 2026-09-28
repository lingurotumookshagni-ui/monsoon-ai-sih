import { useMemo, useState } from 'react'
import KpiCard from '../components/KpiCard'
import RainfallMap from '../components/RainfallMap'
import ForecastTable from '../components/ForecastTable'
import { EmptyState } from '../components/States'
import { useT } from '../i18n'
import { RISK_COLORS, mm, pct } from '../services/constants'

/* Rainfall alerts.

   Only the districts that need attention. This is explicitly NOT the full
   forecast: every other district stays available under All districts, and the
   empty state says so when nothing crosses the threshold. */
export default function Alerts({ rows, onSelectDistrict, onNavigate }) {
  const t = useT()
  const [threshold, setThreshold] = useState(0.2)

  const watchlist = useMemo(
    () =>
      rows
        .filter((r) => (r.heavy_probability || 0) >= threshold ||
                       ['HEAVY', 'VERY_HEAVY'].includes(r.condition))
        .sort((a, b) => b.heavy_probability - a.heavy_probability),
    [rows, threshold],
  )

  const counts = useMemo(() => {
    const out = { LOW: 0, MODERATE: 0, HIGH: 0, VERY_HIGH: 0 }
    rows.forEach((r) => {
      if (out[r.risk_band] !== undefined) out[r.risk_band] += 1
    })
    return out
  }, [rows])

  const labels = {
    district: t('field.district'),
    state: t('field.state'),
    heavy: t('field.heavyProbability'),
    veryHeavy: t('field.veryHeavyProbability'),
    corrected: t('field.rainfall'),
    condition: t('field.condition'),
    risk: t('field.risk'),
    regime: t('field.regime'),
  }

  return (
    <div className="grid page-enter">
      <div className="panel">
        <div className="panel-head">
          <div>
            <h2>{t('alerts.title')}</h2>
            <div className="dim small">{t('alerts.subtitle')}</div>
          </div>
          <span className="panel-note mono">
            {watchlist.length} {t('alerts.count')}
          </span>
        </div>
        <div className="grid kpis stagger">
          <KpiCard label="Very high risk" value={counts.VERY_HIGH} hint="70% and above" accent={RISK_COLORS.VERY_HIGH} />
          <KpiCard label="High risk" value={counts.HIGH} hint="45% to 70%" accent={RISK_COLORS.HIGH} />
          <KpiCard label="Moderate risk" value={counts.MODERATE} hint="20% to 45%" accent={RISK_COLORS.MODERATE} />
          <KpiCard label="Low risk" value={counts.LOW} hint="below 20%" accent={RISK_COLORS.LOW} />
        </div>
      </div>

      <div className="banner">
        <div>
          <strong>Risk bands are a prototype interpretation</strong>
          <div>
            They map model probabilities onto four readable labels and are not official
            warning criteria. Heavy rainfall means 64.5 mm or more in 24 hours; very heavy
            means 115.6 mm or more. Both thresholds are configurable in the backend.
          </div>
        </div>
      </div>

      {watchlist.length ? (
        <>
          <div className="panel">
            <div className="panel-head">
              <h2>{t('alerts.title')}</h2>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <label htmlFor="thr" className="small dim">{t('alerts.minProbability')}</label>
                <input
                  id="thr"
                  type="range"
                  min="0"
                  max="0.9"
                  step="0.05"
                  value={threshold}
                  onChange={(e) => setThreshold(Number(e.target.value))}
                />
                <span className="mono small">{pct(threshold, 0)}</span>
              </div>
            </div>
            <ForecastTable
              rows={watchlist}
              labels={labels}
              columns={['district', 'state', 'heavy', 'veryHeavy', 'corrected', 'condition', 'risk', 'regime']}
              initialSort="heavy_probability"
              onSelect={onSelectDistrict}
            />
            <div className="faint small" style={{ marginTop: 8 }}>
              {t('field.rainfall')}: max {mm(Math.max(0, ...rows.map((r) => r.corrected_mm || 0)))} mm
            </div>
          </div>

          <div className="panel">
            <div className="panel-head">
              <h2>{t('field.heavyProbability')}</h2>
            </div>
            <RainfallMap points={rows} colorBy="risk" onSelect={onSelectDistrict} />
          </div>
        </>
      ) : (
        <EmptyState title={t('alerts.none')} message={t('alerts.noneHint')}>
          <button className="btn primary" onClick={() => onNavigate('all')}>
            {t('nav.allDistricts')}
          </button>
        </EmptyState>
      )}
    </div>
  )
}
