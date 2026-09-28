import {
  Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { REGIME_COLORS, regimeLabel } from '../services/constants'

/* Districts assigned to each regime in the current cycle. */
export default function RegimeDistributionChart({ regimes = [] }) {
  const data = [...regimes]
    .filter((r) => r.districts > 0)
    .sort((a, b) => b.districts - a.districts)
    .map((r) => ({
      regime: r.regime,
      name: regimeLabel(r.regime),
      districts: r.districts,
      avg: r.avg_corrected_mm,
    }))

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 66 }}>
        <CartesianGrid stroke="rgba(122,178,214,0.16)" vertical={false} />
        <XAxis
          dataKey="name"
          angle={-32}
          textAnchor="end"
          interval={0}
          height={84}
          tick={{ fill: '#9db4c6', fontSize: 11 }}
        />
        <YAxis allowDecimals={false} tick={{ fill: '#9db4c6', fontSize: 11 }} width={62} />
        <Tooltip
          contentStyle={{ background: '#0c2337', border: '1px solid rgba(122,178,214,0.34)', borderRadius: 8, color: '#e8f2f8' }}
          formatter={(v, _n, item) => [`${v} districts, mean ${item.payload.avg} mm`, 'Assigned']}
        />
        <Bar dataKey="districts" radius={[3, 3, 0, 0]}>
          {data.map((d) => (
            <Cell key={d.regime} fill={REGIME_COLORS[d.regime] || '#3a82f7'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
