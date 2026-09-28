import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

/* Raw NWP vs AI-corrected rainfall for the wettest districts in the cycle. */
export default function RawVsCorrectedChart({ rows = [], limit = 12 }) {
  const data = [...rows]
    .sort((a, b) => b.corrected_mm - a.corrected_mm)
    .slice(0, limit)
    .map((r) => ({
      district: r.district,
      raw: Number(r.raw_nwp_mm),
      corrected: Number(r.corrected_mm),
    }))

  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: -18, bottom: 46 }}>
        <CartesianGrid stroke="rgba(122,178,214,0.16)" vertical={false} />
        <XAxis
          dataKey="district"
          angle={-38}
          textAnchor="end"
          interval={0}
          height={62}
          tick={{ fill: '#9db4c6', fontSize: 11 }}
        />
        <YAxis tick={{ fill: '#9db4c6', fontSize: 11 }} unit=" mm" width={66} />
        <Tooltip
          contentStyle={{ background: '#0c2337', border: '1px solid rgba(122,178,214,0.34)', borderRadius: 8, color: '#e8f2f8' }}
          formatter={(v, name) => [`${Number(v).toFixed(1)} mm`, name === 'raw' ? 'Raw NWP' : 'AI corrected']}
        />
        <Legend
          formatter={(v) => (v === 'raw' ? 'Raw NWP' : 'AI corrected')}
          wrapperStyle={{ fontSize: 12, color: '#9db4c6' }}
        />
        <Bar dataKey="raw" fill="#4d7a93" radius={[3, 3, 0, 0]} />
        <Bar dataKey="corrected" fill="#2fd4e8" radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
