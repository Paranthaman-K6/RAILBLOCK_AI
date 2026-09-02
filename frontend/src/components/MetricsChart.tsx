import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid } from 'recharts'

export default function MetricsChart({ baseline, optimized }: { baseline: Record<string, unknown>; optimized: Record<string, unknown> }) {
  const b = baseline as Record<string, number>
  const o = optimized as Record<string, number>
  const data = [
    { name: 'Blocks', baseline: b.blocks || 0, optimized: o.blocks || 0 },
    { name: 'Scheduled', baseline: b.scheduled_tasks || 0, optimized: o.scheduled || o.scheduled_tasks || 0 },
    { name: 'Minutes', baseline: b.block_minutes || b.total_block_minutes || 0, optimized: o.block_minutes || o.total_block_minutes || 0 },
  ]
  return (
    <div style={{ height: 250 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} barGap={8}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eef2f6" />
          <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#5a6a7a' }} axisLine={{ stroke: '#e0e6ed' }} tickLine={{ stroke: '#e0e6ed' }} />
          <YAxis tick={{ fontSize: 11, fill: '#5a6a7a' }} axisLine={{ stroke: '#e0e6ed' }} tickLine={{ stroke: '#e0e6ed' }} width={32} />
          <Tooltip cursor={{ fill: 'rgba(45,139,139,0.06)' }} contentStyle={{ borderRadius: 8, border: '1px solid #e0e6ed', fontSize: 12, boxShadow: '0 4px 12px rgba(15,42,68,0.08)' }} />
          <Legend wrapperStyle={{ fontSize: 11, paddingTop: 6 }} />
          <Bar dataKey="baseline" fill="var(--chart-navy)" name="Baseline FCFS" radius={[4, 4, 0, 0]} />
          <Bar dataKey="optimized" fill="var(--chart-teal)" name="CP-SAT Optimized" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
