import { useEffect, useState, useMemo, useCallback } from 'react'
import api from '../services/api'
import { Link } from 'react-router-dom'
import { PrototypeDisclaimer } from '../components/WarningBanner'
import { formatError } from '../services/errors'
import { formatDateKolkata, minutesToTime } from '../services/formatters'
import PlanStatus from '../components/PlanStatus'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid } from 'recharts'
import type { Task, BlockPlan } from '../types'

interface DashboardStats {
  tasks?: number
  windows?: number
  feasible?: number
}

interface HealthData {
  diagnostics?: { journal_mode?: string; path?: string; foreign_keys?: boolean }
  [key: string]: unknown
}

export default function Dashboard(){
  const [stats, setStats]=useState<DashboardStats>({})
  const [plans, setPlans]=useState<BlockPlan[]>([])
  const [health, setHealth]=useState<HealthData | null>(null)
  const [criticalTasks, setCriticalTasks]=useState<Task[]>([])
  const [upcomingBlocks, setUpcomingBlocks]=useState<{block_id:string; service_date:string; corridor_id:string; start_time:number; end_time:number; status?:string}[]>([])
  const [alerts, setAlerts]=useState<string[]>([])
  const [metrics, setMetrics]=useState<Record<string, unknown> & { baseline?: Record<string,number>; optimized?: Record<string,number>; improvement?: Record<string,unknown>; objective_breakdown?: unknown; dataset?: string; asset_availability_pct?: number } | null>(null)
  const [loading, setLoading]=useState(true)
  const [error, setError]=useState('')

  const load=useCallback(async ()=>{
    let cancelled=false
    setLoading(true); setError('')
    try{
      const [h, t, w, p] = await Promise.allSettled([
        api.get('/health'),
        api.get('/api/tasks?limit=100'),
        api.get('/api/windows?status=FEASIBLE'),
        api.get('/api/plans'),
      ])
      if(cancelled) return
      if(h.status==='fulfilled') setHealth((h.value.data as HealthData))
      let derivedCritical: Task[] = []
      if(t.status==='fulfilled'){
        const data = (t.value.data as unknown)
        const tasks: Task[] = Array.isArray(data) ? data as Task[] : ((data as { tasks?: Task[]; total?: number }).tasks || [])
        const count = Array.isArray(data) ? (data as unknown[]).length : ((data as { total?: number; tasks?: unknown[] }).total ?? (data as { tasks?: unknown[] }).tasks?.length ?? 0)
        setStats((s)=>({...s, tasks: count as number}))
        derivedCritical = tasks.filter((ct)=> ct.priority_band==='CRITICAL' || (ct.overdue_days ?? 0) > 10)
        if(!cancelled) setCriticalTasks(derivedCritical.slice(0,5))
      }
      if(w.status==='fulfilled'){
        const data = (w.value.data as unknown)
        setStats((s)=>({...s, windows: Array.isArray(data)? (data as unknown[]).length : (data as { count?: number }).count ?? 0, feasible: Array.isArray(data)? (data as unknown[]).length : 0}))
      }
      if(p.status==='fulfilled'){
        const data = (p.value.data as BlockPlan[])
        setPlans(data)
        if(data.length){
          // Load metrics for latest
          try{
            const m = await api.get(`/api/metrics/${data[0].plan_id}`)
            if(!cancelled) setMetrics(m.data)
          }catch(_e){ /* metrics optional */ }
          // Upcoming blocks: next 7 days from latest approved plan
          const approved = data.find((pl)=>['APPROVED','PUBLISHED'].includes(pl.status))
          if(approved){
            try{
              const pv = await api.get(`/api/plans/${approved.plan_id}`).then(r=>r.data as { blocks?: { block_id:string; service_date:string; corridor_id:string; start_time:number; end_time:number; status?:string }[] })
              const now = new Date('2026-09-01')
              const upcomingFiltered = (pv.blocks || []).filter((b)=>{
                const d = new Date(b.service_date)
                const diff = (d.getTime() - now.getTime())/(1000*60*60*24)
                return diff>=0 && diff<=7
              }).slice(0,5)
              if(!cancelled) setUpcomingBlocks(upcomingFiltered)
            }catch(_e){ /* upcoming optional */ }
          }
          // Alerts: pending approvals, overdue, validation failures
          const pending = data.filter((pl)=>pl.status==='UNDER_REVIEW').length
          const newAlerts:string[]=[]
          if(pending) newAlerts.push(`${pending} plan(s) pending approval (UNDER_REVIEW)`)
          if(derivedCritical.length) newAlerts.push(`${derivedCritical.length} critical/overdue tasks need attention`)
          if(data.some((pl)=>pl.solver_status==='VALIDATION_FAILED')) newAlerts.push(`Validation failed for some plans`)
          if(!cancelled) setAlerts(newAlerts)
        }
      }
    }catch(e: unknown){ if(!cancelled) setError(formatError(e)) }
    finally{ if(!cancelled) setLoading(false)}
    return ()=>{cancelled=true}
  }, [])

  useEffect(()=>{ load(); const id=setInterval(load, 30000); return ()=>clearInterval(id)},[load])

  const healthColor = useMemo(()=> health?.diagnostics?.journal_mode==='wal' ? '#4caf50' : '#ff9800', [health])
  const healthHealthy = health?.diagnostics?.journal_mode==='wal' && health?.diagnostics?.foreign_keys
  const latestApproved = useMemo(()=> plans.find((p)=>['APPROVED','PUBLISHED'].includes(p.status)), [plans])

  const baselineVsOptData = useMemo(()=>{
    if(!metrics) return []
    const m = metrics as { baseline?: Record<string,number>; optimized?: Record<string,number> }
    return [
      { name: 'Blocks', baseline: (m.baseline as Record<string,number>)?.blocks ?? 0, optimized: (m.optimized as Record<string,number>)?.blocks ?? 0 },
      { name: 'Tasks', baseline: (m.baseline as Record<string,number>)?.tasks_scheduled ?? 0, optimized: (m.optimized as Record<string,number>)?.tasks_scheduled ?? 0 },
      { name: 'Minutes', baseline: (m.baseline as Record<string,number>)?.total_block_minutes ?? 0, optimized: (m.optimized as Record<string,number>)?.total_block_minutes ?? 0 },
    ]
  }, [metrics])

  return <div className="page-wrap">
    <div className="page-header">
      <h1>Dashboard</h1>
      <div className="page-subtitle">Human-approved planning prototype · Horizon 2026-09-01→30 · WAL · Synthetic</div>
    </div>
    <PrototypeDisclaimer />
    {loading && <div style={{display:'flex',alignItems:'center',gap:8,padding:'10px 12px',background:'#e3f2fd',border:'1px solid #bbdefb',borderRadius:4,marginTop:8}}><span className="spinner" aria-hidden /><span style={{fontSize:12.5,color:'#0f2a44'}}>Loading live data…</span></div>}
    {error && <div style={{background:'#fef2f2', padding:'10px 12px', border:'1px solid #fecaca', color:'#7a1a1a', marginTop:8, borderRadius:4, fontSize:12.5}}>{error} — Backend may be unavailable. Check /health</div>}
    {!health && !loading && !error && <div style={{background:'#fff8e1', padding:'10px 12px', border:'1px solid #ffecb3', color:'#7a4a00', marginTop:8, borderRadius:4, fontSize:12.5}}>API unavailable — backend not reachable. Check /health</div>}

    <div style={{display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(260px, 1fr))', gap:12, marginTop:12}}>
      {/* Health & DB */}
      <div className="rb-card rb-card--accent">
        <h3 className="rb-card-title">Health &amp; DB</h3>
        <div className="rb-card-desc">SQLite WAL · Prototype diagnostics</div>
        <div style={{display:'flex', alignItems:'center', gap:8, flexWrap:'wrap'}}>
          <span style={{width:10,height:10,background:healthColor,borderRadius:'50%',display:'inline-block',flexShrink:0,boxShadow:`0 0 0 4px ${healthColor}22`}} aria-hidden />
          <span className="pill" style={{background: healthHealthy ? '#e8f5e9' : '#fff3e0', color: healthHealthy ? '#1b5e20' : '#7a3e00', borderColor: healthHealthy ? '#c8e6c9' : '#ffe0b2'}}>
            {health ? (healthHealthy ? 'Healthy · WAL' : 'Degraded') : (loading ? 'Checking…' : 'Unreachable')}
          </span>
          {health?.diagnostics?.journal_mode && <span className="mono-pill" style={{fontSize:10.5}}>journal_mode: {health.diagnostics.journal_mode}</span>}
          {typeof health?.diagnostics?.foreign_keys === 'boolean' && <span className="mono-pill" style={{fontSize:10.5}}>fk: {String(health.diagnostics.foreign_keys)}</span>}
        </div>
        {health?.diagnostics?.path && (
          <div style={{marginTop:8}}>
            <span className="mono-pill mono-pill--teal" title={health.diagnostics.path as string} style={{display:'inline-block',maxWidth:'100%',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap',verticalAlign:'middle'}}>
              {(health.diagnostics.path as string).replace(/^[A-Za-z]:[\\/][^:]*railblock\.db$/,'railblock.db')}
            </span>
          </div>
        )}
        {health?.diagnostics ? (
          <details style={{marginTop:10, background:'#f8fafb', border:'1px solid #eef2f6', borderRadius:4, padding:'6px 8px'}}>
            <summary style={{fontSize:11.5, fontWeight:700, cursor:'pointer', color:'var(--text-secondary)', letterSpacing:0.2}}>Diagnostics</summary>
            <pre className="mono" style={{fontSize:11, lineHeight:1.4, maxHeight:200, overflow:'auto', margin:'8px 0 0', background:'white', border:'1px solid #e0e6ed', borderRadius:4, padding:8}}>{JSON.stringify(health, null, 2)}</pre>
          </details>
        ) : (
          <div style={{marginTop:10, fontSize:11.5, color:'var(--text-muted)'}}>{loading ? 'Awaiting diagnostics…' : 'No diagnostics — Check /health'}</div>
        )}
        <div style={{fontSize:10.5, color:'var(--text-muted)', marginTop:8, lineHeight:1.4}}>SQLite WAL only · No live railway APIs · Checks: health, diagnostics, tasks, windows, plans, metrics</div>
      </div>

      {/* Live Counts */}
      <div className="rb-card">
        <h3 className="rb-card-title">Live Counts</h3>
        <div className="rb-card-desc">Auto-refresh 30s · Synthetic seed 42</div>
        <div className="metric-row">
          <span className="metric-pill">Tasks {stats.tasks ?? '—'}</span>
          <span className="metric-pill">Windows {stats.windows ?? '—'}</span>
          <span className="metric-pill">Feasible {stats.feasible ?? '—'}</span>
          <span className="metric-pill">Plans {plans.length}</span>
        </div>
        <div style={{fontSize:10.5, color:'var(--text-muted)', marginTop:8, lineHeight:1.4}}>
          30 synthetic tasks · 168 total windows · 134 feasible · synthetic data only<br/>
          Horizon 2026-09-01→30 · Latest solver: <span className="mono-pill" style={{fontSize:10, padding:'1px 5px'}}>{plans[0]?.solver_status || '—'}</span>
        </div>
      </div>

      {/* Critical & Overdue */}
      <div className="rb-card">
        <h3 className="rb-card-title">Critical &amp; Overdue</h3>
        <div className="rb-card-desc">Top 5 · CRITICAL or overdue &gt; 10d</div>
        {criticalTasks.length===0 ? <div className="empty-state" style={{padding:12}}>No critical overdue — all tasks within band</div> :
          <div style={{display:'flex', flexDirection:'column', gap:6}}>
            {criticalTasks.map((t)=>{
              const isCritical = t.priority_band==='CRITICAL'
              const bandColor = isCritical ? '#f44336' : t.priority_band==='HIGH' ? '#ff9800' : '#607d8b'
              const pillClass = isCritical ? 'pill--red' : 'pill--amber'
              return (
                <div key={t.task_id} style={{display:'flex', alignItems:'center', gap:8, padding:'7px 8px', background:'white', border:'1px solid #eef2f6', borderRadius:4, borderLeft:`3px solid ${bandColor}`}}>
                  <span className="mono-pill" style={{fontSize:11}}>{t.task_id}</span>
                  <span className={`pill ${pillClass}`} style={{fontSize:10}}>{t.priority_band}</span>
                  <span style={{fontSize:11, color:'var(--text-secondary)', marginLeft:'auto', display:'flex', gap:6, alignItems:'center', flexWrap:'wrap'}}>
                    <span className="mono" style={{fontSize:11, fontWeight:700}}>{t.priority_score}</span>
                    <span>overdue {t.overdue_days}d</span>
                  </span>
                </div>
              )
            })}
          </div>
        }
        <div style={{fontSize:10.5, color:'var(--text-muted)', marginTop:8}}>From <span className="mono-pill" style={{fontSize:10}}>GET /api/tasks?limit=100</span></div>
      </div>
    </div>

    <div style={{display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(320px, 1fr))', gap:12, marginTop:12}}>
      <div className="rb-card">
        <h3 className="rb-card-title">Latest Approved Plan</h3>
        <div className="rb-card-desc">Human-approved · Published to departments</div>
        {latestApproved ?
          <div>
            <div style={{display:'flex', gap:6, flexWrap:'wrap', alignItems:'center'}}>
              <span className="mono-pill">{latestApproved.plan_id}</span>
              <PlanStatus status={latestApproved.status} solver={latestApproved.solver_status} />
              <span className="pill pill--muted" style={{fontSize:11}}>{latestApproved.horizon_type}</span>
            </div>
            <div style={{fontSize:12, color:'var(--text-secondary)', marginTop:8, lineHeight:1.5}}>
              Horizon: <span className="mono" style={{fontSize:12, fontWeight:600}}>{formatDateKolkata(latestApproved.start_date)} → {formatDateKolkata(latestApproved.end_date)}</span><br/>
              Solver: <span className="mono-pill" style={{fontSize:10.5}}>{latestApproved.solver_status}</span>
            </div>
            <div style={{display:'flex', gap:6, flexWrap:'wrap', marginTop:10}}>
              <Link to="/departments" className="btn btn-ghost btn-sm">Departments</Link>
              <Link to="/execution" className="btn btn-ghost btn-sm">Execute</Link>
              <Link to="/metrics" className="btn btn-ghost btn-sm">Metrics</Link>
            </div>
          </div> : <div className="empty-state">None — generate weekly/monthly in <Link to="/planner">Planner</Link></div>
        }
      </div>
      <div className="rb-card">
        <h3 className="rb-card-title">Upcoming Blocks</h3>
        <div className="rb-card-desc">Next 7 days from 2026-09-01 · Approved plan only</div>
        {upcomingBlocks.length===0 ? <div className="empty-state">No upcoming — generate a plan first.</div> :
          <div className="rb-table-wrap">
            <table className="rb-table">
              <thead><tr><th>Block</th><th>Date</th><th>Corridor</th><th>Time</th></tr></thead>
              <tbody>
                {upcomingBlocks.map((b)=><tr key={b.block_id}>
                  <td><span className="mono-pill" style={{fontSize:10.5}}>{b.block_id}</span></td>
                  <td style={{fontSize:12, whiteSpace:'nowrap'}}>{formatDateKolkata(b.service_date)}</td>
                  <td><span className="pill pill--blue" style={{fontSize:10.5}}>{b.corridor_id}</span></td>
                  <td className="mono" style={{fontSize:11, whiteSpace:'nowrap'}}>{minutesToTime(b.start_time)}–{minutesToTime(b.end_time)}</td>
                </tr>)}
              </tbody>
            </table>
          </div>
        }
      </div>
      <div className="rb-card">
        <h3 className="rb-card-title">Department Alerts</h3>
        <div className="rb-card-desc">Signals requiring officer attention</div>
        {alerts.length===0 ? <div style={{display:'flex',alignItems:'center',gap:6,padding:'8px 10px',background:'#e8f5e9',border:'1px solid #c8e6c9',borderRadius:4,color:'#1b5e20',fontSize:12.5,fontWeight:600}}>● No alerts — all clear</div> :
          <div style={{display:'flex',flexDirection:'column',gap:6}}>
            {alerts.map((a,i)=><div key={i} className="pill pill--red" style={{justifyContent:'flex-start',padding:'6px 10px',borderRadius:4,whiteSpace:'normal',lineHeight:1.3,fontSize:12}}>{a}</div>)}
          </div>
        }
        <div style={{fontSize:10.5, color:'var(--text-muted)', marginTop:8}}>Derived from UNDER_REVIEW + critical tasks + VALIDATION_FAILED</div>
      </div>
    </div>

    <div className="rb-card">
      <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', gap:8, flexWrap:'wrap'}}>
        <div>
          <h3 className="rb-card-title" style={{marginBottom:2}}>Baseline vs Optimized</h3>
          <div className="rb-card-desc" style={{marginBottom:0}}>From DB, not hard-coded · <span className="mono" style={{fontSize:11}}>GET /api/metrics/{'{id}'}</span></div>
        </div>
        {metrics && <span className="pill pill--green" style={{fontSize:11}}>Live DB</span>}
      </div>
      {!plans.length ? <div className="empty-state" style={{marginTop:10}}>No plans yet — generate one in <Link to="/planner">Planner</Link> (WEEKLY 2026-09-01 to 2026-09-07)</div> :
        !metrics ? (
          <div style={{marginTop:10}}>
            <div className="skeleton" style={{height:220, borderRadius:8}} />
            <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, marginTop:8}}>
              <div className="skeleton skeleton-card" style={{margin:0, height:84}} />
              <div className="skeleton skeleton-card" style={{margin:0, height:84}} />
            </div>
            <div style={{fontSize:10.5, color:'var(--text-muted)', marginTop:6}}>Fetching metrics for {plans[0]?.plan_id}…</div>
          </div>
        ) : (
        <div style={{marginTop:10}}>
          <div style={{height:220, border:'1px solid #eef2f6', borderRadius:8, padding:'8px 4px 0', background:'white'}}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={baselineVsOptData} barGap={6}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2f6" />
                <XAxis dataKey="name" tick={{fontSize:11, fill:'#5a6a7a'}} axisLine={{stroke:'#e0e6ed'}} tickLine={{stroke:'#e0e6ed'}} />
                <YAxis tick={{fontSize:11, fill:'#5a6a7a'}} axisLine={{stroke:'#e0e6ed'}} tickLine={{stroke:'#e0e6ed'}} width={32} />
                <Tooltip cursor={{fill:'rgba(45,139,139,0.06)'}} contentStyle={{borderRadius:8, border:'1px solid #e0e6ed', fontSize:12, boxShadow:'0 4px 12px rgba(15,42,68,0.08)'}} />
                <Legend wrapperStyle={{fontSize:11, paddingTop:6}} />
                <Bar dataKey="baseline" fill="var(--chart-navy)" name="Baseline FCFS" radius={[4,4,0,0]} />
                <Bar dataKey="optimized" fill="var(--chart-teal)" name="CP-SAT Optimized" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div style={{display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(260px, 1fr))', gap:8, marginTop:10}}>
            <div className="rb-card rb-card--dense" style={{margin:0, background:'#f8fafb'}}>
              <div style={{fontSize:10.5, fontWeight:700, letterSpacing:0.4, textTransform:'uppercase', color:'var(--text-secondary)', marginBottom:6}}>Baseline / Optimized / Improvement</div>
              <pre className="mono" style={{fontSize:11, lineHeight:1.4, margin:0, whiteSpace:'pre-wrap', wordBreak:'break-word', background:'white', border:'1px solid #e0e6ed', borderRadius:4, padding:8, maxHeight:160, overflow:'auto'}}>{JSON.stringify({baseline: (metrics as Record<string,unknown>).baseline, optimized: (metrics as Record<string,unknown>).optimized, improvement: (metrics as Record<string,unknown>).improvement}, null, 2)}</pre>
            </div>
            <div className="rb-card rb-card--dense" style={{margin:0, background:'#f0f7f7'}}>
              <div style={{fontSize:10.5, fontWeight:700, letterSpacing:0.4, textTransform:'uppercase', color:'var(--text-secondary)', marginBottom:6}}>Objective · Dataset · Availability</div>
              <pre className="mono" style={{fontSize:11, lineHeight:1.4, margin:0, whiteSpace:'pre-wrap', wordBreak:'break-word', background:'white', border:'1px solid #e0e6ed', borderRadius:4, padding:8, maxHeight:160, overflow:'auto'}}>{JSON.stringify({objective_breakdown: (metrics as Record<string,unknown>).objective_breakdown, dataset: (metrics as Record<string,unknown>).dataset, asset_availability_pct: (metrics as Record<string,unknown>).asset_availability_pct}, null, 2)}</pre>
            </div>
          </div>
        </div>
        )
      }
      <div style={{fontSize:10.5, color:'var(--text-muted)', marginTop:8, lineHeight:1.4}}>Metrics via <span className="mono-pill" style={{fontSize:10}}>GET /api/metrics/{'{id}'}</span> — real DB state, includes asset_downtime/available/availability_pct, completion_rate, planned/actual/variance</div>
    </div>

    <div className="rb-card">
      <h3 className="rb-card-title">Workflow Stepper</h3>
      <div className="rb-card-desc">Where you are · Synthetic prototype — no live TMS/SMMS/TDMS/COA</div>
      <ol style={{listStyle:'none', margin:0, padding:0, borderLeft:'2px solid var(--teal)', marginLeft:12, paddingLeft:0}}>
        {[
          {title:'Import Data → Validate', link:'/import', label:'Import Page', done: plans.length>0},
          {title:'Prioritize', link:'/tasks', label:'Task Inbox (P=0.30S+…)', done:true},
          {title:'Generate Weekly / Monthly / Daily', link:'/planner', label: plans.length ? plans[0].plan_id : 'Planner', done: plans.length>0},
          {title:'Review → Approve → Publish', link:'/departments', label:'CONTROL_OFFICE final', done: !!latestApproved},
          {title:'Department Views', link:'/departments', label:'my / integrated', done: !!latestApproved},
          {title:'Execute', link:'/execution', label:'Execution (BLK-* 201)', done:false},
          {title:'Metrics', link:'/metrics', label:'baseline vs optimized', done: !!metrics},
        ].map((step, idx)=>(
          <li key={idx} style={{display:'flex', gap:10, alignItems:'flex-start', padding:'8px 0 8px 0', marginLeft:-13}}>
            <span style={{
              width:24, height:24, minWidth:24, borderRadius:'50%',
              background: step.done ? 'var(--teal)' : 'white',
              color: step.done ? 'white' : 'var(--text-muted)',
              border: `2px solid ${step.done ? 'var(--teal)' : '#d0d8e4'}`,
              display:'inline-flex', alignItems:'center', justifyContent:'center',
              fontSize:11, fontWeight:800, lineHeight:1, flexShrink:0
            }}>{step.done ? '✓' : idx+1}</span>
            <div style={{flex:1, minWidth:0, paddingTop:1}}>
              <div style={{fontSize:12.5, fontWeight:600, color:'var(--text-primary)', lineHeight:1.3}}>
                {idx+1}. {step.title} → <Link to={step.link} style={{fontWeight:700}}>{step.label}</Link>
                <span style={{marginLeft:6, fontSize:11, color: step.done ? '#2e7d32' : 'var(--text-muted)'}}>{step.done ? '✓' : '○'}</span>
              </div>
            </div>
          </li>
        ))}
      </ol>
      <div style={{fontSize:10.5, color:'var(--text-muted)', marginTop:8}}>Synthetic prototype: All steps use synthetic data. No live TMS/SMMS/TDMS/COA.</div>
    </div>
  </div>
}
