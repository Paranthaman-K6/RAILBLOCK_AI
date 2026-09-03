import { minutesToTime } from '../services/formatters'
import PlanStatus from './PlanStatus'
import type { Block } from '../types'

interface GanttProps {
  blocks: Block[]
}

export default function Gantt({ blocks }: GanttProps) {
  if (!blocks || blocks.length === 0) return <div className="empty-state">No blocks — no feasible windows or all tasks filtered by safety/deadline.</div>
  return (
    <div className="rb-table-wrap">
      <table className="rb-table">
        <thead>
          <tr>
            <th>Block</th>
            <th>Date</th>
            <th>Time</th>
            <th>Corridor</th>
            <th>Tasks</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {blocks.map((b) => (
            <tr key={b.block_id}>
              <td>
                <span className="mono-pill" style={{ fontSize: 11 }}>
                  {b.block_id}
                </span>
              </td>
              <td className="mono" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>
                {b.service_date}
              </td>
              <td className="mono" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>
                {minutesToTime(b.start_time)}–{minutesToTime(b.end_time)}
              </td>
              <td>
                <span className="pill pill--blue" style={{ fontSize: 11 }}>
                  {b.corridor_id}
                </span>
                {(b.section_id || b.line_id) && (
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-muted)', marginLeft: 6, whiteSpace: 'nowrap' }}>
                    {[b.section_id, b.line_id].filter(Boolean).join(' · ')}
                  </span>
                )}
              </td>
              <td style={{ fontSize: 11, lineHeight: 1.3 }}>
                {(b.tasks ?? []).length ? (
                  <span className="mono" style={{ fontSize: 11, background: '#f8fafb', padding: '2px 6px', borderRadius: 4, border: '1px solid #eef2f6', wordBreak: 'break-word' }}>
                    {(b.tasks ?? []).map((t: unknown) => typeof t === 'string' ? t : ((t as { task_id?: string; id?: string }).task_id || (t as { id?: string }).id || '')).join(', ')}
                  </span>
                ) : (
                  <span style={{ color: 'var(--text-muted)' }}>—</span>
                )}
              </td>
              <td>
                <PlanStatus status={b.status ?? 'UNKNOWN'} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
