import RegimeDistributionChart from '../charts/RegimeDistributionChart'
import { REGIME_COLORS, mm, pct, regimeLabel, signed } from '../services/constants'
import { useT } from '../i18n'

/* Weather regime page: what the classifier decided, and how each regime's
   correction model behaved in this cycle. */
export default function Regimes({ regimeCatalog, overview }) {
  const t = useT()
  const catalogue = regimeCatalog?.regimes || []
  const totalDistricts = overview?.kpis?.districts || 0

  return (
    <div className="grid page-enter">
      <div className="panel">
        <div className="panel-head">
          <h2>Regime classification for this cycle</h2>
          <span className="panel-note">
            {catalogue.filter((r) => r.current?.districts > 0).length} of {catalogue.length} regimes
            are active across {totalDistricts} districts
          </span>
        </div>
        <p className="small dim" style={{ marginBottom: 0 }}>
          A random forest classifies each district from humidity, temperature, pressure, wind speed
          and direction, elevation, distance from coast, position and season. The regime then selects
          which correction model post-processes that district's rainfall. Regime classes are
          project-defined prototype classes, not official meteorological regime definitions.
        </p>
      </div>

      <div className="grid three stagger">
        {catalogue.map((entry) => {
          const c = entry.current || {}
          const share = totalDistricts ? (c.districts || 0) / totalDistricts : 0
          return (
            <div
              className={`regime-card${c.districts ? '' : ' idle'}`}
              key={entry.regime}
              style={{ borderTopColor: REGIME_COLORS[entry.regime] }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'baseline' }}>
                <h3>{t(`regime.${entry.regime}`) || entry.label || regimeLabel(entry.regime)}</h3>
                <span className="mono small" style={{ color: REGIME_COLORS[entry.regime] }}>
                  {c.districts || 0}
                </span>
              </div>
              <p className="desc">{entry.description}</p>
              <div className="bar-track">
                <div
                  className="bar-fill"
                  style={{ width: `${Math.round(share * 100)}%`, background: REGIME_COLORS[entry.regime] }}
                />
              </div>
              <div className="regime-stats">
                <div><span className="dim">Districts</span><b>{c.districts || 0}</b></div>
                <div><span className="dim">Mean rainfall</span><b>{mm(c.avg_corrected_mm)} mm</b></div>
                <div><span className="dim">Mean correction</span><b>{signed(c.avg_correction_mm)} mm</b></div>
                <div><span className="dim">Mean confidence</span><b>{pct(c.avg_confidence)}</b></div>
                <div><span className="dim">Raw NWP mean</span><b>{mm(c.avg_raw_mm)} mm</b></div>
                <div><span className="dim">Heavy alerts</span><b>{c.heavy_alerts || 0}</b></div>
              </div>
              {c.states?.length ? (
                <div className="faint small">{c.states.slice(0, 6).join(', ')}</div>
              ) : (
                <div className="faint small">Not diagnosed anywhere in this cycle</div>
              )}
            </div>
          )
        })}
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2>Regime distribution</h2>
          <span className="panel-note">districts assigned to each regime</span>
        </div>
        <RegimeDistributionChart regimes={overview?.regimes || []} />
      </div>
    </div>
  )
}
