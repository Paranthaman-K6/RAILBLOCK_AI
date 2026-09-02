import { useEffect, useState, useCallback } from 'react'
import api from '../services/api'
import Card from '../components/Card'
import { formatError } from '../services/errors'
import type { Task } from '../types'

const BAND_BORDER: Record<string, string> = {
  CRITICAL: '#f44336',
  HIGH: '#ff9800',
  MEDIUM: '#1976d2',
  LOW: '#8896a8',
}
const BAND_PILL: Record<string, string> = {
  CRITICAL: 'pill--red',
  HIGH: 'pill--amber',
  MEDIUM: 'pill--blue',
  LOW: 'pill--muted',
}

export default function TaskInbox(){
  const [tasks, setTasks]=useState<Task[]>([])
  const [filterDept, setFilterDept]=useState('')
  const [filterCorr, setFilterCorr]=useState('')
  const [loading, setLoading]=useState(false)
  const [error, setError]=useState('')

  const load=useCallback(()=>{
    setLoading(true); setError('')
    const params: Record<string, string>={}
    if(filterDept) params.department=filterDept
    if(filterCorr) params.corridor=filterCorr
    api.get('/api/tasks',{params}).then(r=>{
      const data = r.data as Task[] | { tasks?: Task[] }
      setTasks(Array.isArray(data) ? data : (data.tasks || []))
    }).catch((e: unknown)=> setError(formatError(e as never))).finally(()=> setLoading(false))
  }, [filterDept, filterCorr])

  useEffect(()=>{load()},[load])

  const sorted = [...tasks].sort((a,b)=> (b.priority_score ?? 0) - (a.priority_score ?? 0))

  return <div className="page-wrap">
    <div className="page-header">
      <h1>Task Inbox</h1>
      <div className="page-subtitle">P=0.30S+0.20U+0.20C+0.15O+0.10D+0.05R + historical execution delta · Prioritized workload</div>
    </div>

    <div className="filter-bar">
      <div className="rb-field">
        <label htmlFor="ti-dept">Department</label>
        <select id="ti-dept" className="rb-select" value={filterDept} onChange={e=>setFilterDept(e.target.value)}>
          <option value="">All</option>
          <option value="ENGINEERING">ENGINEERING</option>
          <option value="S_AND_T">S_AND_T</option>
          <option value="TRACTION">TRACTION</option>
        </select>
      </div>
      <div className="rb-field">
        <label htmlFor="ti-corr">Corridor</label>
        <input id="ti-corr" className="rb-input" placeholder="COR-1" value={filterCorr} onChange={e=>setFilterCorr(e.target.value)} />
      </div>
      <button onClick={load} className="btn btn-teal" style={{alignSelf:'flex-end'}}>Filter</button>
      <span className="pill pill--count" style={{marginLeft:'auto', alignSelf:'flex-end'}}>{tasks.length} tasks</span>
    </div>

    {loading && <div style={{display:'grid', gap:10}}>
      {[0,1,2].map(i=> <div key={i} className="skeleton skeleton-card" style={{height:92, borderRadius:8}}><div className="skeleton skeleton-line" style={{width:'40%', height:12, margin:12}} /><div className="skeleton skeleton-line" style={{width:'70%', height:10, margin:'0 12px'}} /><div className="skeleton skeleton-line" style={{width:'55%', height:10, margin:'8px 12px'}} /></div>)}
    </div>}
    {error && <div role="alert" style={{color:'#7a1a1a', background:'#ffebee', padding:'10px 12px', marginTop:10, border:'1px solid #ffcdd2', borderRadius:4, fontSize:12.5}}>{error}</div>}

    {!loading && !error && sorted.length===0 && <div className="empty-state" style={{marginTop:10}}>No tasks match filter</div>}

    {!loading && sorted.length>0 && <div style={{display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(360px, 1fr))', gap:12, marginTop:12}}>
      {sorted.map((t)=>{
        const border = BAND_BORDER[t.priority_band] || '#8896a8'
        const pill = BAND_PILL[t.priority_band] || 'pill--muted'
        return (
          <Card key={t.task_id} title="" className="rb-card--dense" style={{margin:0, borderLeft:`3px solid ${border}`}}>
            <div style={{display:'flex', gap:6, flexWrap:'wrap', alignItems:'center', marginBottom:8}}>
              <span className="mono-pill">{t.task_id}</span>
              <span className={`pill ${pill}`} style={{fontSize:11}}>{t.priority_band}</span>
              <span className="mono-pill mono-pill--teal" title="priority_score">{t.priority_score}</span>
              <span className="pill pill--blue" style={{fontSize:11}}>{t.corridor_id}</span>
            </div>
            <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:12, fontSize:12, color:'var(--text-secondary)', lineHeight:1.5}}>
              <div>Dept <strong style={{color:'var(--text-primary)'}}>{t.department}</strong></div>
              <div style={{fontFamily:'var(--mono)', fontSize:11, color:'var(--text-primary)'}}> {t.corridor_id} {t.section_id ? `· ${t.section_id}` : ''} {t.line_id ? `· ${t.line_id}` : ''} </div>
              <div>Type <span className="pill pill--muted" style={{fontSize:11}}>{t.task_type || '—'}</span> Severity {t.severity || '—'}</div>
              <div>Duration <span className="mono" style={{fontWeight:700, color:'var(--text-primary)'}}>{t.estimated_duration_minutes ?? '—'}m</span></div>
              <div style={{display:'flex', gap:6, alignItems:'center', flexWrap:'wrap'}}>Power <span className={`pill ${t.requires_power_isolation?'pill--amber':'pill--muted'}`} style={{fontSize:10.5}}>{t.requires_power_isolation?'YES':'NO'}</span> Signal <span className={`pill ${t.requires_signal_disconnection?'pill--amber':'pill--muted'}`} style={{fontSize:10.5}}>{t.requires_signal_disconnection?'YES':'NO'}</span></div>
              <div style={{fontSize:11, color:'var(--text-muted)'}}>Score <span className="mono" style={{fontWeight:700, color:'var(--text-primary)'}}>{t.priority_score}</span></div>
            </div>
            <div style={{fontSize:12, color:'var(--text-secondary)', marginTop:8, lineHeight:1.4}}><span style={{fontSize:10.5, fontWeight:700, letterSpacing:0.4, textTransform:'uppercase', color:'var(--text-secondary)'}}>Reason</span> <span style={{color:'var(--text-primary)'}}>{t.priority_reason || '—'}</span></div>
            <details style={{marginTop:8, background:'#f8fafb', border:'1px solid #eef2f6', borderRadius:4, padding:'6px 8px'}}>
              <summary style={{fontSize:11, fontWeight:700, cursor:'pointer', color:'var(--text-secondary)'}}>Details</summary>
              <pre className="mono" style={{fontSize:11, lineHeight:1.4, maxHeight:160, overflow:'auto', margin:'8px 0 0', background:'white', border:'1px solid #e0e6ed', borderRadius:4, padding:8, whiteSpace:'pre-wrap', wordBreak:'break-word'}}>{JSON.stringify(t,null,2)}</pre>
            </details>
          </Card>
        )
      })}
    </div>}
  </div>
}
