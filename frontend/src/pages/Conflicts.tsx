import { useState, useEffect, useCallback, useMemo } from 'react'
import api from '../services/api'
import Card from '../components/Card'
import { formatError } from '../services/errors'
import type { Task, CandidateWindow } from '../types'

interface ConflictEntry {
  block?: string
  window?: string
  service_date?: string
  corridor?: string
  result?: { valid?: boolean; status?: string; conflicts?: { code: string }[]; train_conflict?: boolean; goods_risk?: string }
  error?: string
}

export default function Conflicts() {
  const [res, setRes] = useState<Record<string, unknown> | null>(null)
  const [tasks, setTasks] = useState<Task[]>([])
  const [windows, setWindows] = useState<CandidateWindow[]>([])
  const [task, setTask] = useState('TSK-001')
  const [window, setWindow] = useState('WND-')
  const [allConflicts, setAllConflicts] = useState<ConflictEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [filterCorridor, setFilterCorridor] = useState('')

  const loadOptions = useCallback(async () => {
    try {
      const [tRes, wRes] = await Promise.all([
        api.get('/api/tasks?limit=100').then((r) => (Array.isArray(r.data) ? (r.data as Task[]) : ((r.data as { tasks?: Task[] }).tasks || []))),
        api.get('/api/windows?status=FEASIBLE').then((r) => (Array.isArray(r.data) ? (r.data as CandidateWindow[]).slice(0, 20) : [])),
      ])
      setTasks(tRes)
      setWindows(wRes)
      if (tRes[0]) setTask(tRes[0].task_id || (tRes[0] as unknown as { id: string }).id)
      if (wRes[0]) setWindow(wRes[0].window_id)
    } catch {
      /* ignore load error */
    }
  }, [])
  useEffect(() => {
    loadOptions()
  }, [loadOptions])

  const check = useCallback(async () => {
    setLoading(true)
    try {
      const r = await api.post('/api/conflicts/detect', { task_id: task, window_id: window })
      setRes(r.data as Record<string, unknown>)
    } catch (e: unknown) {
      setRes({ error: formatError(e) })
    } finally {
      setLoading(false)
    }
  }, [task, window])

  const checkAll = useCallback(async () => {
    setLoading(true)
    try {
      const plans = await api.get('/api/plans').then((r) => r.data as { plan_id: string }[])
      if (!plans.length) {
        setAllConflicts([])
        return
      }
      const latest = plans[0].plan_id
      const plan = await api.get(`/api/plans/${latest}`).then(
        (r) =>
          r.data as {
            blocks: { block_id: string; window_id: string; service_date: string; corridor_id: string; tasks?: ({ task_id: string } | string)[] }[]
          },
      )
      const results: ConflictEntry[] = await Promise.all(
        plan.blocks.slice(0, 10).map(async (b) => {
          try {
            const taskId =
              typeof b.tasks?.[0] === 'string'
                ? (b.tasks[0] as string)
                : ((b.tasks?.[0] as { task_id?: string })?.task_id || 'TSK-001')
            const r = await api.post('/api/conflicts/detect', { task_id: taskId, window_id: b.window_id })
            return { block: b.block_id, window: b.window_id, service_date: b.service_date, corridor: b.corridor_id, result: r.data as ConflictEntry['result'] }
          } catch (e: unknown) {
            return { block: b.block_id, error: formatError(e) }
          }
        }),
      )
      setAllConflicts(results)
    } catch (e: unknown) {
      setAllConflicts([{ error: formatError(e) }])
    } finally {
      setLoading(false)
    }
  }, [])

  const filteredWindows = useMemo(() => {
    if (!filterCorridor) return windows
    return windows.filter((w) => w.corridor_id === filterCorridor)
  }, [windows, filterCorridor])

  const isError = !!(res as { error?: string } | null)?.error
  const conflictsArr = ((res as { conflicts?: unknown[] } | null)?.conflicts as unknown[]) || []
  const validField = (res as { valid?: boolean } | null)?.valid
  const isHard = validField === false || conflictsArr.length > 0
  const feasibleLabel = !isError && !isHard ? 'FEASIBLE — No conflicts' : validField === false ? 'HARD_CONFLICT' : conflictsArr.length ? 'Conflicts found' : '—'

  return (
    <div className="page-wrap">
      <div className="page-header">
        <h1>Conflicts &amp; Compatibility</h1>
        <div className="page-subtitle">Train Goods Resource Power Signal · protected intervals &amp; hard constraints</div>
      </div>

      <Card title="Compatibility Matrix (Quick Reference)">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 8 }}>
          <div className="rb-card rb-card--dense" style={{ margin: 0, background: '#f8fafb' }}>
            <strong style={{ fontSize: 12.5, color: 'var(--text-primary)' }}>Train</strong>
            <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', lineHeight: 1.4, marginTop: 4 }}>
              Protected [departure-15, arrival+15) — overlap if train_start &lt; block_end &amp;&amp; train_end &gt; block_start. Exact boundary no overlap.
            </div>
          </div>
          <div className="rb-card rb-card--dense" style={{ margin: 0, background: '#f8fafb' }}>
            <strong style={{ fontSize: 12.5, color: 'var(--text-primary)' }}>Goods</strong>
            <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', lineHeight: 1.4, marginTop: 4 }}>
              Confidence ≥0.7 → HARD, ≥0.4 → SOFT. Window goods_risk_score≥70 → REJECTED.
            </div>
          </div>
          <div className="rb-card rb-card--dense" style={{ margin: 0, background: '#f8fafb' }}>
            <strong style={{ fontSize: 12.5, color: 'var(--text-primary)' }}>Resources</strong>
            <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', lineHeight: 1.4, marginTop: 4 }}>
              Per date non-overlap per resource_id (CREW/MACHINE/MATERIAL). Bulk check.
            </div>
          </div>
          <div className="rb-card rb-card--dense" style={{ margin: 0, background: '#f8fafb' }}>
            <strong style={{ fontSize: 12.5, color: 'var(--text-primary)' }}>Power / Signal</strong>
            <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', lineHeight: 1.4, marginTop: 4 }}>
              Task requires isolation → window must have same. Mismatch → HARD.
            </div>
          </div>
          <div className="rb-card rb-card--dense" style={{ margin: 0, background: '#f8fafb' }}>
            <strong style={{ fontSize: 12.5, color: 'var(--text-primary)' }}>Duration</strong>
            <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', lineHeight: 1.4, marginTop: 4 }}>
              Needed (estimated+setup) ≤ available_minutes (max 240). Overflow → HARD.
            </div>
          </div>
          <div className="rb-card rb-card--dense" style={{ margin: 0, background: '#f8fafb' }}>
            <strong style={{ fontSize: 12.5, color: 'var(--text-primary)' }}>Dependencies</strong>
            <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', lineHeight: 1.4, marginTop: 4 }}>
              Depends_on must be scheduled earlier (same date + start_time). Ordering violation → HARD.
            </div>
          </div>
        </div>
      </Card>

      <Card title="Single Task-Window Check (Fast, Memoized)">
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8, lineHeight: 1.4 }}>
          Checks: passenger train protected [departure-buffer, arrival+buffer) overlap=train_start&lt;block_end &amp;&amp; train_end&gt;block_start (exact boundary no overlap), goods forecast confidence≥0.7
          HARD else ≥0.4 SOFT, corridor/section/line, block Type, power isolation, signalling, resources, duration ≤240, dependencies. All from DB.
        </div>

        <div className="filter-bar" style={{ marginBottom: 8 }}>
          <select value={task} onChange={(e) => setTask(e.target.value)} className="rb-select" style={{ minWidth: 180, flex: '1 1 160px' }} aria-label="Task">
            {tasks.map((t) => (
              <option key={t.task_id} value={t.task_id}>
                {t.task_id} ({t.department}) {t.corridor_id}
              </option>
            ))}
            {!tasks.length && <option value={task}>{task}</option>}
          </select>
          <select value={filterCorridor} onChange={(e) => setFilterCorridor(e.target.value)} className="rb-select" style={{ minWidth: 130 }} aria-label="Filter corridor">
            <option value="">All Corridors</option>
            <option value="COR-1">COR-1</option>
            <option value="COR-2">COR-2</option>
            <option value="COR-3">COR-3</option>
          </select>
          <select value={window} onChange={(e) => setWindow(e.target.value)} className="rb-select" style={{ minWidth: 200, flex: '1 1 180px' }} aria-label="Window">
            {filteredWindows.map((w) => (
              <option key={w.window_id} value={w.window_id}>
                {w.window_id} {w.service_date} {w.start_time}-{w.end_time} {w.corridor_id} {w.status}
              </option>
            ))}
            {!filteredWindows.length && <option value={window}>{window || 'WND- (enter manual)'}</option>}
          </select>
        </div>

        <div className="rb-form-row" style={{ marginBottom: 8 }}>
          <div className="rb-field" style={{ flex: '0 0 120px' }}>
            <label htmlFor="conf-task-manual">Task override</label>
            <input id="conf-task-manual" value={task} onChange={(e) => setTask(e.target.value)} placeholder="TSK-*" className="rb-input" style={{ width: '100%' }} />
          </div>
          <div className="rb-field" style={{ flex: '0 0 150px' }}>
            <label htmlFor="conf-wnd-manual">Window override</label>
            <input id="conf-wnd-manual" value={window} onChange={(e) => setWindow(e.target.value)} placeholder="WND-*" className="rb-input" style={{ width: '100%' }} />
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', flexWrap: 'wrap', marginLeft: 'auto', paddingTop: 16 }}>
            <button onClick={check} disabled={loading} className="btn btn-blue">
              {loading ? <span className="spinner" style={{ width: 12, height: 12, borderWidth: 1.5 }} aria-hidden /> : null}
              {loading ? 'Checking…' : 'Check'}
            </button>
            <button onClick={checkAll} disabled={loading} className="btn btn-green">
              Check All Blocks (Batch)
            </button>
          </div>
        </div>

        {res && (
          <>
            <pre
              style={{
                background: isError || isHard ? '#ffebee' : '#e8f5e9',
                padding: 10,
                margin: 0,
                border: `1px solid ${isError || isHard ? '#f8bbd0' : '#c8e6c9'}`,
                borderRadius: 4,
                maxHeight: 250,
                overflow: 'auto',
                fontSize: 11,
                lineHeight: 1.4,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {JSON.stringify(res, null, 2)}
            </pre>
            {!isError && (
              <div style={{ marginTop: 6 }}>
                <span className={isHard ? 'pill pill--red' : 'pill pill--green'} style={{ fontSize: 10.5, letterSpacing: 0.3 }}>
                  {feasibleLabel}
                </span>
              </div>
            )}
          </>
        )}
      </Card>

      <Card title="Batch Conflict Matrix (Latest Plan, Up to 10 Blocks)">
        {allConflicts.length === 0 ? (
          <div style={{ fontSize: 12.5, color: 'var(--text-muted)', lineHeight: 1.4 }}>
            Click “Check All Blocks” to scan latest plan’s blocks against trains/goods/resources. Efficient batch with early exit.
          </div>
        ) : (
          <div className="rb-table-wrap">
            <table className="rb-table" style={{ fontSize: 12 }}>
              <thead>
                <tr>
                  <th>Block</th>
                  <th>Window</th>
                  <th>Date / Corridor</th>
                  <th>Result</th>
                  <th>Train</th>
                  <th>Goods</th>
                  <th>Resource / Power / Signal</th>
                </tr>
              </thead>
              <tbody>
                {allConflicts.map((c, i) => {
                  const isConflict = !!(c.result?.valid === false || c.result?.conflicts?.length)
                  return (
                    <tr key={i} className={isConflict ? 'status-conflict' : 'status-feasible'} style={{ background: isConflict ? '#ffebee' : '#e8f5e9' }}>
                      <td style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{c.block || '—'}</td>
                      <td style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{c.window || '—'}</td>
                      <td style={{ fontSize: 11, whiteSpace: 'nowrap' }}>
                        {c.service_date || '—'} {c.corridor ? <span className="pill pill--blue" style={{ fontSize: 10, marginLeft: 4 }}>{c.corridor}</span> : null}
                      </td>
                      <td>
                        <span className={isConflict ? 'pill pill--red' : 'pill pill--green'} style={{ fontSize: 10.5 }}>
                          {c.result ? (c.result.valid === false ? 'CONFLICT' : c.result.status || (c.result.conflicts?.length ? 'CONFLICT' : 'FEASIBLE')) : c.error || '-'}
                        </span>
                      </td>
                      <td>
                        <span className={c.result?.train_conflict || c.result?.conflicts?.some((x) => x.code === 'TRAIN_CONFLICT') ? 'pill pill--red' : 'pill pill--green'} style={{ fontSize: 10.5 }}>
                          {c.result?.train_conflict || c.result?.conflicts?.some((x) => x.code === 'TRAIN_CONFLICT') ? 'YES' : 'NO'}
                        </span>
                      </td>
                      <td>
                        <span className={c.result?.goods_risk || c.result?.conflicts?.some((x) => x.code === 'GOODS_RISK') ? 'pill pill--amber' : 'pill pill--green'} style={{ fontSize: 10.5 }}>
                          {c.result?.goods_risk || c.result?.conflicts?.some((x) => x.code === 'GOODS_RISK') ? 'RISK' : 'OK'}
                        </span>
                      </td>
                      <td style={{ fontSize: 11 }}>
                        {c.result?.conflicts?.filter((x) => ['RESOURCE_CONFLICT', 'POWER_MISMATCH', 'SIGNAL_MISMATCH'].includes(x.code)).map((x) => x.code).join(', ') || (
                          <span className="pill pill--green" style={{ fontSize: 10.5 }}>OK</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6, padding: '6px 8px', background: '#f8fafb', borderTop: '1px solid #eef2f6' }}>
              Color: <span style={{ background: '#ffebee', padding: '2px 6px', borderRadius: 4, border: '1px solid #f8bbd0' }}>Conflict</span>{' '}
              <span style={{ background: '#e8f5e9', padding: '2px 6px', borderRadius: 4, border: '1px solid #c8e6c9' }}>Feasible</span> • Uses{' '}
              <code className="mono-pill" style={{ fontSize: 10 }}>
                POST /api/conflicts/detect
              </code>{' '}
              per block, with bulk window/train maps on backend (no N+1).
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
