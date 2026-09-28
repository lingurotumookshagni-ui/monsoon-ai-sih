import {
  Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { CATEGORY_COLORS, CATEGORY_ORDER, CATEGORY_RANGES, categoryLabel } from '../services/constants'

/* How many districts fall in each rainfall class, before and after correction. */
export default function DistributionChart({ rows = [], field = 'category' }) {
  const data = CATEGORY_ORDER.map((c) => ({
    category: categoryLabel(c),
    key: c,
    districts: rows.filter((r) => r[field] === c).length,
    range: CATEGORY_RANGES[c],
  }))

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 24 }}>
        <CartesianGrid stroke="rgba(122,178,214,0.16)" vertical={false} />
        <XAxis dataKey="category" tick={{ fill: '#9db4c6', fontSize: 11 }} interval={0} height={44} />
        <YAxis allowDecimals={false} tick={{ fill: '#9db4c6', fontSize: 11 }} width={62} />
        <Tooltip
          contentStyle={{ background: '#0c2337', border: '1px solid rgba(122,178,214,0.34)', borderRadius: 8, color: '#e8f2f8' }}
          formatter={(v, _n, item) => [`${v} districts (${item.payload.range})`, 'Count']}
        />
        <Bar dataKey="districts" radius={[3, 3, 0, 0]}>
          {data.map((d) => (
            <Cell key={d.key} fill={CATEGORY_COLORS[d.key]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
