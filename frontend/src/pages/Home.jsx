import { useState } from 'react'
import KpiCard from '../components/KpiCard'
import RainfallMap from '../components/RainfallMap'
import DistributionChart from '../charts/DistributionChart'
import RegimeDistributionChart from '../charts/RegimeDistributionChart'
import { ConditionPill } from '../components/Pill'
import { useT } from '../i18n'
import { CONDITION_ORDER, mm, num } from '../services/constants'

/* Home: three obvious doors into the product, then the current cycle at a
   glance. The three actions come first because most visitors want one
   question answered - what is the rainfall in my district. */
export default function Home({ overview, rows, onNavigate, onSelectDistrict }) {
  const t = useT()
  const [selected, setSelected] = useState(null)
  const kpis = overview?.kpis || {}
  const ver = overview?.verification || { available: false }
  const conditions = kpis.conditions || {}

  const actions = [
    {
      id: 'check',
      icon: '🌧️',
      accent: '#2fd4e8',
      title: t('home.checkTitle'),
      sub: t('home.checkSubtitle'),
    },
    {
      id: 'alerts',
      icon: '⚠️',
      accent: '#f2a63b',
      title: t('home.alertsTitle'),
      sub: t('home.alertsSubtitle'),
    },
    {
      id: 'postprocessing',
      icon: '📊',
      accent: '#8b6df2',
      title: t('home.analysisTitle'),
      sub: t('home.analysisSubtitle'),
    },
  ]

  const openDistrict = (district) => {
    setSelected(district)
    if (onSelectDistrict) onSelectDistrict(district)
  }

  return (
    <div className="grid page-enter">
      <div>
        <h2 style={{ marginBottom: 10 }}>{t('home.title')}</h2>
        <div className="action-grid stagger">
          {actions.map((action) => (
            <button
              key={action.id}
              className="action-card"
              style={{ '--accent': action.accent }}
              onClick={() => onNavigate(action.id)}
            >
              <span className="action-icon" aria-hidden="true">{action.icon}</span>
              <span className="action-title">{action.title}</span>
              <span className="action-sub">{action.sub}</span>
              <span className="action-go">{t('home.open')}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2>{t('home.cycleTitle')}</h2>
          <span className="panel-note">
            {CONDITION_ORDER.filter((c) => conditions[c]).map((c) => (
              <span key={c} style={{ marginLeft: 6 }}>
                <ConditionPill condition={c} /> <span className="mono">{conditions[c]}</span>
              </span>
            ))}
          </span>
        </div>
        <div className="grid kpis stagger">
          <KpiCard label={t('kpi.districts')} value={kpis.districts ?? '-'} accent="#2fd4e8" />
          <KpiCard label={t('kpi.heavyAlerts')} value={kpis.heavy_alerts ?? '-'} accent="#f2a63b" />
          <KpiCard label={t('kpi.veryHeavyAlerts')} value={kpis.very_heavy_alerts ?? '-'} accent="#d62246" />
          <KpiCard label={t('kpi.activeRegimes')} value={kpis.active_regimes ?? '-'} accent="#8b6df2" />
          <KpiCard
            label={t('kpi.rawRmse')}
            value={ver.available ? num(ver.raw_rmse, 2) : t('technical.notAvailable')}
            unit={ver.available ? 'mm' : ''}
            accent="#4d7a93"
          />
          <KpiCard
            label={t('kpi.aiRmse')}
            value={ver.available ? num(ver.ai_rmse, 2) : t('technical.notAvailable')}
            unit={ver.available ? 'mm' : ''}
            hint={ver.available && ver.rmse_reduction_pct != null ? `${ver.rmse_reduction_pct}%` : undefined}
            accent="#34d39b"
          />
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2>{t('common.districts')}</h2>
          <span className="panel-note">
            {t('all.showing', { shown: rows.length, total: rows.length })}. Mean{' '}
            {mm(kpis.mean_corrected_mm)} mm.
          </span>
        </div>
        <RainfallMap points={rows} onSelect={openDistrict} selected={selected} />
      </div>

      <div className="grid two">
        <div className="panel">
          <div className="panel-head"><h2>{t('field.category')}</h2></div>
          <DistributionChart rows={rows} />
        </div>
        <div className="panel">
          <div className="panel-head"><h2>{t('nav.regimes')}</h2></div>
          <RegimeDistributionChart regimes={overview?.regimes || []} />
        </div>
      </div>
    </div>
  )
}
