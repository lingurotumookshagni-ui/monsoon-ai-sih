import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip } from 'react-leaflet'
import {
  CATEGORY_COLORS,
  CATEGORY_ORDER,
  RISK_COLORS,
  categoryLabel,
  mm,
  pct,
  regimeLabel,
} from '../services/constants'

/* District rainfall map. Marker colour encodes the rainfall category (or the
   heavy-rain risk band), marker radius encodes the corrected amount, so the
   spatial pattern of the correction is readable at a glance. */

function radiusFor(value) {
  const v = Math.max(0, Number(value) || 0)
  return 5 + Math.min(16, Math.sqrt(v) * 1.15)
}

export default function RainfallMap({
  points = [],
  colorBy = 'category',
  onSelect,
  selected,
  tall = false,
}) {
  const valid = points.filter((p) => Number.isFinite(p.lat) && Number.isFinite(p.lon))
  const center = valid.length
    ? [
        valid.reduce((a, p) => a + p.lat, 0) / valid.length,
        valid.reduce((a, p) => a + p.lon, 0) / valid.length,
      ]
    : [20.6, 79.0]

  const colorOf = (p) =>
    colorBy === 'risk'
      ? RISK_COLORS[p.risk_band] || '#63b7e8'
      : CATEGORY_COLORS[p.category] || '#63b7e8'

  return (
    <div>
      <div className={tall ? 'map-shell tall' : 'map-shell'}>
        <MapContainer center={center} zoom={5} scrollWheelZoom minZoom={4} maxZoom={10}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {valid.map((p) => {
            const isSelected = selected && selected.district === p.district
            return (
              <CircleMarker
                key={`${p.district}-${p.state}`}
                center={[p.lat, p.lon]}
                radius={radiusFor(p.corrected_mm)}
                pathOptions={{
                  color: isSelected ? '#ffffff' : colorOf(p),
                  weight: isSelected ? 3 : 1.4,
                  fillColor: colorOf(p),
                  fillOpacity: 0.62,
                }}
                eventHandlers={{ click: () => onSelect && onSelect(p) }}
              >
                <Tooltip direction="top" offset={[0, -4]}>
                  {p.district}: {mm(p.corrected_mm)} mm
                </Tooltip>
                <Popup>
                  <strong>{p.district}</strong>
                  <div className="faint small">{p.state}</div>
                  <div style={{ marginTop: 6 }}>
                    Regime: {regimeLabel(p.regime)} ({pct(p.regime_confidence)})
                    <br />
                    Raw NWP: {mm(p.raw_nwp_mm)} mm
                    <br />
                    AI corrected: {mm(p.corrected_mm)} mm
                    <br />
                    Heavy rain probability: {pct(p.heavy_probability)}
                    <br />
                    Category: {categoryLabel(p.category)}
                  </div>
                </Popup>
              </CircleMarker>
            )
          })}
        </MapContainer>
      </div>
      <div className="legend">
        {(colorBy === 'risk' ? Object.keys(RISK_COLORS) : CATEGORY_ORDER).map((key) => (
          <span key={key}>
            <i
              className="swatch"
              style={{
                background: colorBy === 'risk' ? RISK_COLORS[key] : CATEGORY_COLORS[key],
              }}
            />
            {colorBy === 'risk' ? key.replace('_', ' ').toLowerCase() : categoryLabel(key)}
          </span>
        ))}
        <span className="faint">Circle size scales with corrected rainfall</span>
      </div>
    </div>
  )
}
