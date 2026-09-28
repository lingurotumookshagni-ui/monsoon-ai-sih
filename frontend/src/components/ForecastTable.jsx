import { useMemo, useState } from 'react'
import { CategoryPill, ConditionPill, RiskPill } from './Pill'
import { mm, pct, regimeLabel, signed } from '../services/constants'

/* Sortable district forecast table. Columns are declared by the page so the
   same table serves the forecast list and the heavy-rainfall watchlist. */

const COLUMNS = {
  district: { label: 'District', sort: 'district' },
  state: { label: 'State', sort: 'state' },
  regime: { label: 'Regime', sort: 'regime' },
  raw: { label: 'Raw NWP', unit: 'mm', num: true, sort: 'raw_nwp_mm' },
  corrected: { label: 'AI corrected', unit: 'mm', num: true, sort: 'corrected_mm' },
  change: { label: 'Change', unit: 'mm', num: true, sort: 'correction_mm' },
  heavy: { label: 'Heavy rain probability', num: true, sort: 'heavy_probability' },
  veryHeavy: { label: 'Very heavy probability', num: true, sort: 'very_heavy_probability' },
  category: { label: 'Category', sort: 'category' },
  condition: { label: 'Condition', sort: 'corrected_mm' },
  risk: { label: 'Risk', sort: 'heavy_probability' },
  confidence: { label: 'Regime confidence', num: true, sort: 'regime_confidence' },
}

export default function ForecastTable({
  rows = [],
  labels = {},
  columns = ['district', 'state', 'regime', 'raw', 'corrected', 'change', 'heavy', 'category'],
  initialSort = 'corrected_mm',
  onSelect,
  selected,
  maxRows = 200,
}) {
  const [sortKey, setSortKey] = useState(initialSort)
  const [asc, setAsc] = useState(false)

  const sorted = useMemo(() => {
    const out = [...rows].sort((a, b) => {
      const x = a[sortKey]
      const y = b[sortKey]
      if (typeof x === 'string' || typeof y === 'string') {
        return String(x).localeCompare(String(y))
      }
      return (Number(x) || 0) - (Number(y) || 0)
    })
    return asc ? out : out.reverse()
  }, [rows, sortKey, asc])

  const clickHeader = (key) => {
    if (!key) return
    if (key === sortKey) setAsc(!asc)
    else {
      setSortKey(key)
      setAsc(key === 'district' || key === 'state')
    }
  }

  const cell = (key, row) => {
    switch (key) {
      case 'district':
        return <td key={key}>{row.district}</td>
      case 'state':
        return <td key={key} className="dim">{row.state}</td>
      case 'regime':
        return (
          <td key={key}>
            <span className="regime-tag">{regimeLabel(row.regime)}</span>
          </td>
        )
      case 'raw':
        return <td key={key} className="num">{mm(row.raw_nwp_mm)}</td>
      case 'corrected':
        return <td key={key} className="num">{mm(row.corrected_mm)}</td>
      case 'change':
        return (
          <td key={key} className={`num ${row.correction_mm >= 0 ? 'delta-up' : 'delta-down'}`}>
            {signed(row.correction_mm)}
          </td>
        )
      case 'heavy':
        return <td key={key} className="num">{pct(row.heavy_probability, 1)}</td>
      case 'veryHeavy':
        return <td key={key} className="num">{pct(row.very_heavy_probability, 1)}</td>
      case 'confidence':
        return <td key={key} className="num">{pct(row.regime_confidence)}</td>
      case 'category':
        return <td key={key}><CategoryPill category={row.category} /></td>
      case 'condition':
        return <td key={key}><ConditionPill condition={row.condition} /></td>
      case 'risk':
        return <td key={key}><RiskPill band={row.risk_band} /></td>
      default:
        return <td key={key}>-</td>
    }
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((key) => {
              const col = COLUMNS[key]
              return (
                <th
                  key={key}
                  className={`sortable${col.num ? ' num' : ''}`}
                  onClick={() => clickHeader(col.sort)}
                  title={`Sort by ${(labels[key] || col.label).toLowerCase()}`}
                >
                  {labels[key] || col.label}
                  {col.unit ? <span className="faint"> ({col.unit})</span> : null}
                  {col.sort === sortKey ? <span className="faint">{asc ? ' \u2191' : ' \u2193'}</span> : null}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.slice(0, maxRows).map((row) => (
            <tr
              key={`${row.district}-${row.state}`}
              className={selected && selected.district === row.district ? 'selected' : undefined}
              onClick={() => onSelect && onSelect(row)}
              style={onSelect ? { cursor: 'pointer' } : undefined}
            >
              {columns.map((key) => cell(key, row))}
            </tr>
          ))}
        </tbody>
      </table>
      {sorted.length > maxRows ? (
        <div className="faint small" style={{ padding: '8px 10px' }}>
          Showing the first {maxRows} of {sorted.length} districts. Narrow the filters to see the rest.
        </div>
      ) : null}
    </div>
  )
}
