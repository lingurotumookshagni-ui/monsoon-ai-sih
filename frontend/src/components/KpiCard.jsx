/* One instrument readout: label, value, unit and a short qualifier. */
export default function KpiCard({ label, value, unit, hint, accent }) {
  return (
    <div className="kpi" style={accent ? { '--accent': accent } : undefined}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">
        {value}
        {unit ? <span className="kpi-unit">{unit}</span> : null}
      </div>
      {hint ? <div className="kpi-hint">{hint}</div> : null}
    </div>
  )
}
