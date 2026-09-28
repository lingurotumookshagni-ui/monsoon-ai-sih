import { useState } from 'react'
import { ConditionPill } from './Pill'
import { useT } from '../i18n'
import { mm, num, pct, signed } from '../services/constants'

/* The citizen-facing district result: big number, condition, one plain
   sentence, then optional technical detail for judges and forecasters.
   Nothing is invented here - a value the backend did not provide is shown as
   "Not available" instead of a made-up number. */
export default function DistrictResult({ record, regime, verification, defaultOpen = false }) {
  const t = useT()
  const [showTech, setShowTech] = useState(defaultOpen)
  if (!record) return null

  const condition = record.condition || 'UNKNOWN'
  const regimeCode = record.regime || regime?.code
  const na = t('technical.notAvailable')

  const value = (v, suffix, digits = 1) =>
    v === null || v === undefined ? na : `${mm(v, digits)}${suffix ? ` ${suffix}` : ''}`

  const technical = [
    [t('field.rawForecast'), value(record.raw_nwp_mm, 'mm')],
    [t('field.correctedForecast'), value(record.corrected_mm, 'mm')],
    [t('field.correction'), record.correction_mm === undefined ? na : `${signed(record.correction_mm)} mm`],
    [t('field.regimeConfidence'), record.regime_confidence === undefined || record.regime_confidence === null ? na : pct(record.regime_confidence, 1)],
    [t('field.veryHeavyProbability'), record.very_heavy_probability === undefined || record.very_heavy_probability === null ? na : pct(record.very_heavy_probability, 1)],
    [t('field.humidity'), value(record.humidity, '%')],
    [t('field.pressure'), value(record.pressure, 'hPa')],
    [t('field.windSpeed'), value(record.wind_speed, 'm/s')],
    [t('field.elevation'), value(record.elevation, 'm', 0)],
    [t('field.coastDistance'), value(record.distance_from_coast, 'km', 0)],
  ]

  const scores = verification && verification.available !== false
    ? [
        ['RMSE', num(verification.ai_corrected?.rmse, 2)],
        ['CSI', num(verification.ai_corrected?.csi, 3)],
        ['POD', num(verification.ai_corrected?.pod, 3)],
        ['FAR', num(verification.ai_corrected?.far, 3)],
        ['ETS', num(verification.ai_corrected?.ets, 3)],
        ['FSS', num(verification.ai_corrected?.fss, 3)],
      ]
    : null

  return (
    <div className="result-card">
      <div className="result-head">
        <div>
          <div className="result-district">{record.district}</div>
          <div className="faint small">{record.state}</div>
        </div>
        <ConditionPill condition={condition} />
      </div>

      <div className="result-figure">
        <span className="result-value">{mm(record.corrected_mm)}</span>
        <span className="result-unit">mm</span>
      </div>
      <div className="dim small">{t('field.rainfall')}</div>

      <div className="result-grid">
        <div className="result-item">
          <div className="label">{t('field.heavyProbability')}</div>
          <div className="value">
            {record.heavy_probability === undefined || record.heavy_probability === null
              ? na
              : pct(record.heavy_probability, 0)}
          </div>
        </div>
        <div className="result-item">
          <div className="label">{t('field.regime')}</div>
          <div className="value" style={{ fontSize: '0.98rem' }}>
            {regimeCode ? t(`regime.${regimeCode}`) : na}
          </div>
        </div>
        <div className="result-item">
          <div className="label">{t('field.condition')}</div>
          <div className="value" style={{ fontSize: '0.98rem' }}>{t(`condition.${condition}`)}</div>
        </div>
        {record.forecast_date ? (
          <div className="result-item">
            <div className="label">{t('field.date')}</div>
            <div className="value" style={{ fontSize: '0.98rem' }}>{record.forecast_date}</div>
          </div>
        ) : null}
      </div>

      <div className="simple-explain">
        <strong>{t('simple.title')}</strong>
        <div>{t(`explanation.${condition}`)}</div>
      </div>

      {regime?.description ? (
        <p className="small dim" style={{ marginTop: 12, marginBottom: 0 }}>
          {regime.description}
        </p>
      ) : null}

      <button
        className="btn"
        style={{ marginTop: 14 }}
        onClick={() => setShowTech(!showTech)}
        aria-expanded={showTech}
      >
        {showTech ? t('technical.hide') : t('technical.show')}
      </button>

      {showTech ? (
        <div style={{ marginTop: 12 }} className="page-enter">
          <h3>{t('technical.title')}</h3>
          <div className="detail-rows">
            {technical.map(([label, val]) => (
              <div className="detail-row" key={label}>
                <span>{label}</span>
                <span>{val}</span>
              </div>
            ))}
          </div>
          {scores ? (
            <div style={{ marginTop: 12 }}>
              <div className="dim small" style={{ marginBottom: 6 }}>
                Verification of the corrected forecast over the evaluation period
                {verification.sample_size ? ` (${verification.sample_size} pairs)` : ''}
              </div>
              <div className="result-grid">
                {scores.map(([name, val]) => (
                  <div className="result-item" key={name}>
                    <div className="label">{name}</div>
                    <div className="value">{val}</div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="faint small" style={{ marginTop: 10 }}>
              RMSE, CSI, POD, FAR, ETS, FSS: {na}
            </div>
          )}
        </div>
      ) : null}
    </div>
  )
}
