import {
  Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { CATEGORY_COLORS } from '../services/constants'

/* Wettest districts after post-processing, coloured by rainfall category. */
export default function TopDistrictsChart({ rows = [], limit = 10 }) {
  const data = [...rows]
    .sort((a, b) => b.corrected_mm - a.corrected_mm)
    .slice(0, limit)
    .map((r) => ({ district: r.district, value: Number(r.corrected_mm), category: r.category }))

  return (
    <ResponsiveContainer width="100%" height={Math.max(220, data.length * 28)}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 24, left: 8, bottom: 4 }}>
        <XAxis type="number" tick={{ fill: '#9db4c6', fontSize: 11 }} unit=" mm" />
        <YAxis
          type="category"
          dataKey="district"
          width={126}
          tick={{ fill: '#9db4c6', fontSize: 11 }}
        />
        <Tooltip
          contentStyle={{ background: '#0c2337', border: '1px solid rgba(122,178,214,0.34)', borderRadius: 8, color: '#e8f2f8' }}
          formatter={(v) => [`${Number(v).toFixed(1)} mm`, 'AI corrected']}
        />
        <Bar dataKey="value" radius={[0, 3, 3, 0]}>
          {data.map((d) => (
            <Cell key={d.district} fill={CATEGORY_COLORS[d.category] || '#3a82f7'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
