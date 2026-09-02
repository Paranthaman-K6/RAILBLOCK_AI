import { useEffect, useState } from 'react'
import api from '../services/api'
import Card from '../components/Card'

type Weights = Record<string, number>

const WEIGHT_META: Record<string, { label: string; desc: string; color: string }> = {
  S: { label: 'Safety', desc: 'severity × safety_score — 30%', color: 'var(--teal)' },
  U: { label: 'Urgency', desc: 'deadline & overdue — 20%', color: '#1976d2' },
  C: { label: 'Criticality', desc: 'asset_criticality — 20%', color: '#7b1fa2' },
  O: { label: 'Operational', desc: 'operational_impact — 15%', color: '#ff9800' },
  D: { label: 'Deadline', desc: 'overdue_days & deadline proximity — 10%', color: '#607d8b' },
  R: { label: 'Readiness', desc: 'coordination & resource_readiness — 5%', color: '#2e7d32' },
}

const COMPONENTS: { title: string; desc: string }[] = [
  { title: 'Feature extraction', desc: 'Parse severity, asset, deadline, location from synthetic TMS/SMMS/TDMS/COA rows' },
  { title: 'Normalized priority', desc: 'P = 0.30S + 0.20U + 0.20C + 0.15O + 0.10D + 0.05R + historical execution delta' },
  { title: 'Goods-risk analysis', desc: 'Confidence ≥0.7 HARD, ≥0.4 SOFT; window goods_risk_score gates feasibility' },
  { title: 'Compatibility reasoning', desc: 'Train / goods / resource / power / signal / duration / dependency hard checks' },
  { title: 'Candidate-window ranking', desc: 'Templates 01:00–03:00, 13:30–15:30, 02:00–06:00; ranked by feasibility & corridor' },
  { title: 'Baseline FCFS', desc: 'First-come first-served greedy assignment for baseline vs optimized comparison' },
  { title: 'CP-SAT optimization', desc: 'OR-Tools CP-SAT, 5s limit, 8 workers, maximizes priority & integrated groups' },
  { title: 'Deterministic fallback', desc: 'If CP-SAT fails/timeouts → deterministic ranking ensures draft always produced' },
  { title: 'Independent validator', desc: '14 checks A–L + grouping; failed validation → no draft persisted' },
]

export default function Optimizer() {
  const [weights, setWeights] = useState<Weights | null>(null)
  const [aiModel, setAiModel] = useState<Record<string, unknown> | null>(null)
  const [showModel, setShowModel] = useState(false)
  const [loadingWeights, setLoadingWeights] = useState(true)

  useEffect(() => {
    setLoadingWeights(true)
    api
      .get('/api/compatibility/priority-weights')
      .then((r) => setWeights(r.data as Weights))
      .catch(() => setWeights(null))
      .finally(() => setLoadingWeights(false))
  }, [])

  const openModel = async () => {
    try {
      const r = await api.get('/api/compatibility/ai-model')
      setAiModel(r.data as Record<string, unknown>)
      setShowModel(true)
    } catch {
      setAiModel({ error: 'Failed to load AI model' })
      setShowModel(true)
    }
  }

  const totalWeight = weights ? (Object.values(weights) as number[]).reduce((a, b) => a + (typeof b === 'number' ? b : 0), 0) : 0

  return (
    <div className="page-wrap">
      <div className="page-header">
        <h1>Optimizer &amp; Hybrid AI</h1>
        <div className="page-subtitle">Human-approved · explainable · baseline vs CP-SAT vs fallback</div>
      </div>

      <Card title="Priority Weights" action={<span className="pill pill--count">P = 0.30S + 0.20U + 0.20C + 0.15O + 0.10D + 0.05R</span>}>
        <div className="rb-card-desc" style={{ marginTop: -2 }}>
          GET /api/compatibility/priority-weights · weights sum to 1.0 · applied before CP-SAT ranking
        </div>
        {loadingWeights ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[0, 1, 2].map((k) => (
              <div key={k} className="skeleton" style={{ height: 28, borderRadius: 4 }} />
            ))}
          </div>
        ) : !weights ? (
          <div className="empty-state">Weights unavailable — backend /api/compatibility/priority-weights not reachable.</div>
        ) : (
          <div className="rb-table-wrap">
            <table className="rb-table">
              <thead>
                <tr>
                  <th>Weight</th>
                  <th>Value</th>
                  <th>Description</th>
                  <th style={{ minWidth: 120 }}>Share</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(weights).map(([key, val]) => {
                  const meta = WEIGHT_META[key] || { label: key, desc: '', color: 'var(--teal)' }
                  const v = typeof val === 'number' ? val : Number(val) || 0
                  const pct = totalWeight ? (v / totalWeight) * 100 : v * 100
                  return (
                    <tr key={key}>
                      <td>
                        <span className="mono-pill" style={{ fontSize: 11, background: '#e3f2fd', borderColor: '#bbdefb', color: '#0d47a1' }}>
                          {key}
                        </span>{' '}
                        <span style={{ fontSize: 12.5, fontWeight: 600 }}>{meta.label}</span>
                      </td>
                      <td className="mono" style={{ fontSize: 12, fontWeight: 700 }}>
                        {typeof val === 'number' ? val.toFixed(2) : String(val)}
                      </td>
                      <td style={{ fontSize: 11.5, color: 'var(--text-secondary)', lineHeight: 1.3 }}>{meta.desc}</td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <div style={{ flex: 1, height: 6, background: '#eef2f6', borderRadius: 99, overflow: 'hidden', minWidth: 60 }}>
                            <div style={{ width: `${pct}%`, height: '100%', background: meta.color, borderRadius: 99 }} />
                          </div>
                          <span className="mono" style={{ fontSize: 11, color: 'var(--text-muted)', minWidth: 32 }}>
                            {pct.toFixed(0)}%
                          </span>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8, lineHeight: 1.4 }}>
          Safety 30% dominates · urgency &amp; criticality 20% each · operational 15% · deadline 10% · readiness 5% · total 1.00
        </div>
      </Card>

      <Card title="Hybrid AI Components" action={<button onClick={openModel} className="btn btn-ghost btn-sm">Show AI Model</button>}>
        <div className="rb-card-desc" style={{ marginTop: -2 }}>
          9-step pipeline · explainable · no unsupervised publication
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 8 }}>
          {COMPONENTS.map((c, idx) => (
            <div key={c.title} className="rb-card rb-card--dense" style={{ margin: 0, display: 'flex', gap: 10, alignItems: 'flex-start', background: '#f8fafb' }}>
              <span
                className="pill"
                style={{
                  background: idx < 3 ? 'var(--teal-50)' : idx < 6 ? '#e3f2fd' : '#fff8e1',
                  color: idx < 3 ? '#0f5a5a' : idx < 6 ? '#0d47a1' : '#7a4a00',
                  borderColor: idx < 3 ? 'var(--teal-100)' : idx < 6 ? '#bbdefb' : '#ffecb3',
                  minWidth: 26,
                  justifyContent: 'center',
                  fontSize: 10.5,
                  fontFamily: 'var(--mono)',
                }}
                aria-hidden
              >
                {idx + 1}
              </span>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.3 }}>{c.title}</div>
                <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', lineHeight: 1.4, marginTop: 2 }}>{c.desc}</div>
              </div>
            </div>
          ))}
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8, lineHeight: 1.4 }}>
          Feature extraction → priority → goods-risk → compatibility → ranking → baseline FCFS → CP-SAT (5s, 8 workers) → fallback → validator (14 checks A–L)
        </div>
      </Card>

      <Card title="Solver &amp; Transparency">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 8 }}>
          <div className="rb-card rb-card--dense" style={{ margin: 0 }}>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.4, textTransform: 'uppercase', color: 'var(--text-secondary)' }}>Baseline</div>
            <div style={{ fontSize: 12.5, fontWeight: 600, marginTop: 2 }}>FCFS Greedy</div>
            <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 2, lineHeight: 1.4 }}>Tasks in priority order, first feasible window. Fast, deterministic.</div>
          </div>
          <div className="rb-card rb-card--dense" style={{ margin: 0, borderTop: '3px solid var(--teal)' }}>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.4, textTransform: 'uppercase', color: 'var(--teal)' }}>Optimized</div>
            <div style={{ fontSize: 12.5, fontWeight: 600, marginTop: 2 }}>CP-SAT · 5s · 8 workers</div>
            <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 2, lineHeight: 1.4 }}>Maximizes weighted priority + integrated groups under hard constraints.</div>
          </div>
          <div className="rb-card rb-card--dense" style={{ margin: 0 }}>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.4, textTransform: 'uppercase', color: 'var(--text-secondary)' }}>Fallback</div>
            <div style={{ fontSize: 12.5, fontWeight: 600, marginTop: 2 }}>Deterministic</div>
            <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 2, lineHeight: 1.4 }}>If CP-SAT fails/timeouts, ranking ensures draft always produced.</div>
          </div>
        </div>
        <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button onClick={openModel} className="btn btn-teal btn-sm">
            View AI Model (GET /api/compatibility/ai-model)
          </button>
          <span style={{ fontSize: 11, color: 'var(--text-muted)', alignSelf: 'center', lineHeight: 1.4 }}>Opens dialog with raw model details · no alert()</span>
        </div>
      </Card>

      {showModel && (
        <div
          className="rb-dialog-backdrop"
          onClick={() => setShowModel(false)}
          role="presentation"
          style={{ cursor: 'pointer' }}
        >
          <div
            className="rb-dialog"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label="AI Model"
            style={{ cursor: 'auto', maxWidth: 640 }}
          >
            <header>
              <h3>AI Model</h3>
              <button onClick={() => setShowModel(false)} className="btn btn-ghost btn-sm" aria-label="Close" style={{ padding: '4px 8px' }}>
                ✕
              </button>
            </header>
            <div className="dialog-body">
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>GET /api/compatibility/ai-model · read-only · synthetic prototype</div>
              <pre
                className="mono"
                style={{
                  background: '#f8fafb',
                  padding: 12,
                  fontSize: 11,
                  lineHeight: 1.4,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  border: '1px solid #eef2f6',
                  borderRadius: 4,
                  margin: 0,
                  maxHeight: '50vh',
                  overflow: 'auto',
                }}
              >
                {aiModel ? JSON.stringify(aiModel, null, 2) : 'Loading…'}
              </pre>
            </div>
            <footer>
              <button onClick={() => setShowModel(false)} className="btn btn-ghost btn-sm">
                Close
              </button>
            </footer>
          </div>
        </div>
      )}
    </div>
  )
}
