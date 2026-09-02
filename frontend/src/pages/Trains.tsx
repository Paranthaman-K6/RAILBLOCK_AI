import { useEffect, useState, useMemo } from 'react'
import api from '../services/api'
import Card from '../components/Card'
import { minutesToTime } from '../services/formatters'
import type { TrainMovement, CandidateWindow } from '../types'

function riskPill(value?: number | string | null) {
  if (value == null || value === '') return <span className="pill pill--muted" style={{ fontSize: 11 }}>—</span>
  const num = typeof value === 'string' ? Number(value) : value
  if (Number.isNaN(num as number)) {
    const s = String(value).toUpperCase()
    if (s.includes('HIGH') || s.includes('REJECT')) return <span className="pill pill--red" style={{ fontSize: 11 }}>{String(value)}</span>
    if (s.includes('MED') || s.includes('SOFT')) return <span className="pill pill--amber" style={{ fontSize: 11 }}>{String(value)}</span>
    return <span className="pill pill--green" style={{ fontSize: 11 }}>{String(value)}</span>
  }
  if ((num as number) >= 70) return <span className="pill pill--red" style={{ fontSize: 11 }}>{num}</span>
  if ((num as number) >= 40) return <span className="pill pill--amber" style={{ fontSize: 11 }}>{num}</span>
  return <span className="pill pill--green" style={{ fontSize: 11 }}>{num}</span>
}

export default function Trains() {
  const [trains, setTrains] = useState<TrainMovement[]>([])
  const [windows, setWindows] = useState<CandidateWindow[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [corridor, setCorridor] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    Promise.all([api.get('/api/trains'), api.get('/api/windows')])
      .then(([tRes, wRes]) => {
        if (cancelled) return
        const tData = tRes.data as TrainMovement[] | { trains?: TrainMovement[] }
        const wData = wRes.data as CandidateWindow[] | { windows?: CandidateWindow[] }
        const tList = Array.isArray(tData) ? tData : (tData as { trains?: TrainMovement[] }).trains || []
        const wList = Array.isArray(wData) ? wData : (wData as { windows?: CandidateWindow[] }).windows || []
        setTrains(tList)
        setWindows(wList)
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const filteredTrains = useMemo(() => {
    const term = search.trim().toLowerCase()
    return trains.filter((t) => {
      const matchSearch = !term || t.train_id.toLowerCase().includes(term) || t.corridor_id.toLowerCase().includes(term)
      const matchCorr = !corridor || t.corridor_id === corridor
      return matchSearch && matchCorr
    })
  }, [trains, search, corridor])

  const filteredWindows = useMemo(() => {
    if (!corridor) return windows
    return windows.filter((w) => w.corridor_id === corridor)
  }, [windows, corridor])

  const windowSlice = useMemo(() => filteredWindows.slice(0, 20), [filteredWindows])

  return (
    <div className="page-wrap">
      <div className="page-header">
        <h1>Trains &amp; Windows</h1>
        <div className="page-subtitle">Timetable · Protected intervals [departure-buffer, arrival+buffer) · Synthetic prototype</div>
      </div>

      <div className="filter-bar">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search train_id…"
          className="rb-input"
          style={{ flex: '1 1 180px', minWidth: 140 }}
          aria-label="Search train"
        />
        <select value={corridor} onChange={(e) => setCorridor(e.target.value)} className="rb-select" style={{ minWidth: 140 }} aria-label="Filter corridor">
          <option value="">All Corridors</option>
          <option value="COR-1">COR-1</option>
          <option value="COR-2">COR-2</option>
          <option value="COR-3">COR-3</option>
        </select>
        <span className="pill pill--count">Trains {trains.length}</span>
        <span className="pill pill--count">Windows {windows.length}</span>
        {corridor && <span className="pill pill--muted" style={{ fontSize: 11 }}>filtered · {filteredWindows.length} windows</span>}
      </div>

      <Card title="Trains" action={<span className="pill pill--count">{filteredTrains.length} shown</span>}>
        <div className="rb-card-desc" style={{ marginTop: -2 }}>
          GET /api/trains · TRN-* · departure / arrival are minutes since midnight · buffer forms protected interval
        </div>
        {loading ? (
          <div className="rb-table-wrap">
            <table className="rb-table">
              <thead>
                <tr>
                  <th>Train</th>
                  <th>Corridor</th>
                  <th>Service Date</th>
                  <th>Departure</th>
                  <th>Arrival</th>
                </tr>
              </thead>
              <tbody>
                {[0, 1, 2].map((k) => (
                  <tr key={k}>
                    <td>
                      <div className="skeleton" style={{ height: 14, width: 80 }} />
                    </td>
                    <td>
                      <div className="skeleton" style={{ height: 14, width: 70 }} />
                    </td>
                    <td>
                      <div className="skeleton" style={{ height: 14, width: 90 }} />
                    </td>
                    <td>
                      <div className="skeleton" style={{ height: 14, width: 50 }} />
                    </td>
                    <td>
                      <div className="skeleton" style={{ height: 14, width: 50 }} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : filteredTrains.length === 0 ? (
          <div className="empty-state">No trains — {search || corridor ? 'no match for current filters.' : 'backend returned none.'}</div>
        ) : (
          <div className="rb-table-wrap">
            <table className="rb-table">
              <thead>
                <tr>
                  <th>Train</th>
                  <th>Corridor</th>
                  <th>Service Date</th>
                  <th>Departure</th>
                  <th>Arrival</th>
                </tr>
              </thead>
              <tbody>
                {filteredTrains.slice(0, 50).map((t) => (
                  <tr key={t.train_id}>
                    <td>
                      <span className="mono-pill" style={{ fontSize: 11 }}>
                        {t.train_id}
                      </span>
                    </td>
                    <td>
                      <span className="pill pill--blue" style={{ fontSize: 11 }}>
                        {t.corridor_id}
                      </span>
                    </td>
                    <td className="mono" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>
                      {t.service_date}
                    </td>
                    <td className="mono" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>
                      {minutesToTime(t.departure_time)}
                    </td>
                    <td className="mono" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>
                      {minutesToTime(t.arrival_time)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filteredTrains.length > 50 && <div style={{ fontSize: 11, color: 'var(--text-muted)', padding: '6px 10px', background: '#f8fafb', borderTop: '1px solid #eef2f6' }}>Showing 50 of {filteredTrains.length} · refine search</div>}
          </div>
        )}
      </Card>

      <Card title="Candidate Windows (Synthetic prototype)" action={<span className="pill pill--count">{windowSlice.length} of {filteredWindows.length}</span>}>
        <div className="rb-card-desc" style={{ marginTop: -2 }}>
          GET /api/windows · WND-* · templates 01:00–03:00, 13:30–15:30, 02:00–06:00 · max 240m · goods risk &amp; status
        </div>
        {loading ? (
          <div className="rb-table-wrap">
            <table className="rb-table">
              <thead>
                <tr>
                  <th>Window</th>
                  <th>Date</th>
                  <th>Time</th>
                  <th>Corridor</th>
                  <th>Section / Line</th>
                  <th>Block Type</th>
                  <th>Goods risk</th>
                  <th>Status</th>
                  <th>Available</th>
                </tr>
              </thead>
              <tbody>
                {[0, 1, 2, 3].map((k) => (
                  <tr key={k}>
                    {Array.from({ length: 9 }).map((_, j) => (
                      <td key={j}>
                        <div className="skeleton" style={{ height: 14, width: 40 + j * 6 }} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : windowSlice.length === 0 ? (
          <div className="empty-state">No windows — {corridor ? `no WND for ${corridor}` : 'backend returned none.'}</div>
        ) : (
          <div className="rb-table-wrap">
            <table className="rb-table">
              <thead>
                <tr>
                  <th>Window</th>
                  <th>Date</th>
                  <th>Time</th>
                  <th>Corridor</th>
                  <th>Section / Line</th>
                  <th>Block Type</th>
                  <th>Goods risk</th>
                  <th>Status</th>
                  <th>Available</th>
                </tr>
              </thead>
              <tbody>
                {windowSlice.map((w) => (
                  <tr key={w.window_id}>
                    <td>
                      <span className="mono-pill mono-pill--teal" style={{ fontSize: 11 }}>
                        {w.window_id}
                      </span>
                    </td>
                    <td className="mono" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>
                      {w.service_date}
                    </td>
                    <td className="mono" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>
                      {minutesToTime(w.start_time)}–{minutesToTime(w.end_time)}
                    </td>
                    <td>
                      <span className="pill pill--blue" style={{ fontSize: 11 }}>
                        {w.corridor_id}
                      </span>
                    </td>
                    <td style={{ fontFamily: 'var(--mono)', fontSize: 11, whiteSpace: 'nowrap' }}>
                      {[w.section_id, w.line_id].filter(Boolean).join(' · ') || '—'}
                    </td>
                    <td>
                      <span className={w.block_type === 'TRAFFIC_BLOCK' ? 'pill pill--amber' : 'pill pill--muted'} style={{ fontSize: 11 }}>
                        {w.block_type}
                      </span>
                    </td>
                    <td>{riskPill(w.goods_risk_score ?? (w as unknown as { goods_risk_score?: number }).goods_risk_score ?? (w as unknown as { risk_band?: string }).risk_band)}</td>
                    <td>
                      <span className={w.status === 'FEASIBLE' ? 'pill pill--green' : w.status === 'REJECTED' ? 'pill pill--red' : 'pill pill--muted'} style={{ fontSize: 11 }}>
                        {w.status}
                      </span>
                    </td>
                    <td className="mono" style={{ fontSize: 11 }}>
                      {w.available_minutes}m
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filteredWindows.length > 20 && (
              <div style={{ fontSize: 11, color: 'var(--text-muted)', padding: '6px 10px', background: '#f8fafb', borderTop: '1px solid #eef2f6' }}>
                Showing 20 of {filteredWindows.length} windows · use corridor filter to narrow · synthetic prototype windows, not official availability
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  )
}
