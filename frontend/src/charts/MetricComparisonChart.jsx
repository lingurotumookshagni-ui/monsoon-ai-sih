import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

/* Raw NWP vs AI-corrected for a set of verification scores. */
export default function MetricComparisonChart({ raw = {}, ai = {}, metrics, height = 300 }) {
  const data = metrics
    .filter((m) => raw[m.key] !== null && raw[m.key] !== undefined)
    .map((m) => ({
      metric: m.label,
      rawValue: Number(raw[m.key]),
      aiValue: ai[m.key] === null || ai[m.key] === undefined ? null : Number(ai[m.key]),
    }))

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 8 }}>
        <CartesianGrid stroke="rgba(122,178,214,0.16)" vertical={false} />
        <XAxis dataKey="metric" tick={{ fill: '#9db4c6', fontSize: 11 }} interval={0} />
        <YAxis tick={{ fill: '#9db4c6', fontSize: 11 }} width={62} />
        <Tooltip
          contentStyle={{ background: '#0c2337', border: '1px solid rgba(122,178,214,0.34)', borderRadius: 8, color: '#e8f2f8' }}
          formatter={(v, name) => [Number(v).toFixed(3), name === 'rawValue' ? 'Raw NWP' : 'AI corrected']}
        />
        <Legend
          formatter={(v) => (v === 'rawValue' ? 'Raw NWP' : 'AI corrected')}
          wrapperStyle={{ fontSize: 12, color: '#9db4c6' }}
        />
        <Bar dataKey="rawValue" fill="#4d7a93" radius={[3, 3, 0, 0]} />
        <Bar dataKey="aiValue" fill="#2fd4e8" radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
