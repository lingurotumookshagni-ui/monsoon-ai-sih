import { useMemo, useState } from 'react'
import ForecastTable from '../components/ForecastTable'
import RawVsCorrectedChart from '../charts/RawVsCorrectedChart'
import TopDistrictsChart from '../charts/TopDistrictsChart'
import DistributionChart from '../charts/DistributionChart'
import { EmptyState } from '../components/States'
import { ConditionPill } from '../components/Pill'
import { useT } from '../i18n'
import { CONDITION_ORDER, REGIME_ORDER, mm } from '../services/constants'

/* All districts.

   This page deliberately lists EVERY district in the active cycle, including
   low and normal rainfall. Heavy rainfall gets its own alerts page; filtering
   the main list down to heavy districts would leave a normal-rainfall user
   with nowhere to look. */
export default function Forecast({ rows, onSelectDistrict }) {
  const t = useT()
  const [search, setSearch] = useState('')
  const [state, setState] = useState('')
  const [regime, setRegime] = useState('')
  const [condition, setCondition] = useState('')

  const states = useMemo(
    () => [...new Set(rows.map((r) => r.state))].filter(Boolean).sort(),
    [rows],
  )

  const filtered = useMemo(
    () =>
      rows.filter(
        (r) =>
          (!search || r.district.toLowerCase().includes(search.trim().toLowerCase())) &&
          (!state || r.state === state) &&
          (!regime || r.regime === regime) &&
          (!condition || r.condition === condition),
      ),
    [rows, search, state, regime, condition],
  )

  const counts = useMemo(() => {
    const out = {}
    rows.forEach((r) => {
      out[r.condition] = (out[r.condition] || 0) + 1
    })
    return out
  }, [rows])

  const clear = () => {
    setSearch('')
    setState('')
    setRegime('')
    setCondition('')
  }

  const hasFilters = search || state || regime || condition

  const labels = {
    district: t('field.district'),
    state: t('field.state'),
    regime: t('field.regime'),
    raw: t('field.rawForecast'),
    corrected: t('field.correctedForecast'),
    change: t('field.change'),
    heavy: t('field.heavyProbability'),
    condition: t('field.condition'),
    category: t('field.category'),
    risk: t('field.risk'),
  }

  return (
    <div className="grid page-enter">
      <div className="panel">
        <div className="panel-head">
          <div>
            <h2>{t('all.title')}</h2>
            <div className="dim small">{t('all.subtitle')}</div>
          </div>
          <span className="panel-note">
            {t('all.showing', { shown: filtered.length, total: rows.length })}
          </span>
        </div>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
          {CONDITION_ORDER.filter((c) => counts[c]).map((c) => (
            <button
              key={c}
              className={`btn${condition === c ? ' active' : ''}`}
              onClick={() => setCondition(condition === c ? '' : c)}
              aria-pressed={condition === c}
            >
              <ConditionPill condition={c} /> <span className="mono">{counts[c]}</span>
            </button>
          ))}
        </div>

        <div className="filters">
          <div className="field">
            <label htmlFor="search">{t('all.search')}</label>
            <input
              id="search"
              type="text"
              value={search}
              placeholder={t('check.searchPlaceholder')}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="state">{t('all.filterState')}</label>
            <select id="state" value={state} onChange={(e) => setState(e.target.value)}>
              <option value="">{t('all.allStates')}</option>
              {states.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="regime">{t('all.filterRegime')}</label>
            <select id="regime" value={regime} onChange={(e) => setRegime(e.target.value)}>
              <option value="">{t('all.allRegimes')}</option>
              {REGIME_ORDER.map((r) => (
                <option key={r} value={r}>{t(`regime.${r}`)}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="condition">{t('all.filterCondition')}</label>
            <select id="condition" value={condition} onChange={(e) => setCondition(e.target.value)}>
              <option value="">{t('all.allConditions')}</option>
              {CONDITION_ORDER.map((c) => (
                <option key={c} value={c}>{t(`condition.${c}`)}</option>
              ))}
            </select>
          </div>
        </div>
        {hasFilters ? (
          <button className="btn" style={{ marginTop: 10 }} onClick={clear}>
            {t('all.clear')}
          </button>
        ) : null}
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2>{t('common.districts')}</h2>
          <span className="panel-note">{t('common.viewDetails')}</span>
        </div>
        {filtered.length ? (
          <ForecastTable
            rows={filtered}
            labels={labels}
            columns={['district', 'state', 'regime', 'raw', 'corrected', 'change', 'heavy', 'condition']}
            onSelect={onSelectDistrict}
          />
        ) : (
          <EmptyState title={t('all.noMatch')} message={t('all.noMatchHint')}>
            <button className="btn" onClick={clear}>{t('all.clear')}</button>
          </EmptyState>
        )}
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2>{t('process.rawVsCorrected')}</h2>
          <span className="panel-note">
            {t('field.correction')}: {mm(average(filtered.length ? filtered : rows, 'correction_mm'))} mm
          </span>
        </div>
        <RawVsCorrectedChart rows={filtered.length ? filtered : rows} />
      </div>

      <div className="grid two">
        <div className="panel">
          <div className="panel-head"><h2>{t('field.rainfall')}</h2></div>
          <TopDistrictsChart rows={filtered.length ? filtered : rows} />
        </div>
        <div className="panel">
          <div className="panel-head"><h2>{t('field.category')}</h2></div>
          <DistributionChart rows={filtered.length ? filtered : rows} />
        </div>
      </div>
    </div>
  )
}

function average(rows, key) {
  if (!rows.length) return 0
  return rows.reduce((a, b) => a + (Number(b[key]) || 0), 0) / rows.length
}
