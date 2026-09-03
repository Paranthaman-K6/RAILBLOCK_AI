import { useEffect, useState } from 'react'
import api from '../services/api'
import Card from '../components/Card'
import Gantt from '../components/Gantt'
import PlanStatus from '../components/PlanStatus'
import ValidationPanel from '../components/ValidationPanel'
import { formatError } from '../services/errors'
import { PrototypeDisclaimer } from '../components/WarningBanner'
import { formatDateKolkata, minutesToTime } from '../services/formatters'
import { HORIZONS } from '../constants/horizons'
import type { BlockPlan, Block } from '../types'

export default function Planner(){
  const [plans, setPlans]=useState<BlockPlan[]>([])
  const [selected, setSelected]=useState<BlockPlan & { blocks?: Block[]; required_departments?: string[]; approved_departments?: string[]; pending_departments?: string[]; approvals?: {approver_role:string; approver_id:string}[]; baseline_metrics?: unknown; optimized_metrics?: unknown; objective_breakdown?: unknown; unscheduled_reasons?: unknown; validation?: unknown } | null>(null)
  const [horizonStart, setHorizonStart]=useState<string>(HORIZONS.WEEKLY.start)
  const [horizonEnd, setHorizonEnd]=useState<string>(HORIZONS.WEEKLY.end)
  const [mode, setMode]=useState<keyof typeof HORIZONS>('WEEKLY')
  const [error, setError]=useState('')
  const [loading, setLoading]=useState(false)
  const [approveDept, setApproveDept]=useState<string>('CONTROL_OFFICE')
  // Plans list: GET /api/plans returns all including DRAFT; View must handle DRAFT reliably
  const load=()=> api.get('/api/plans').then(r=>setPlans(r.data as BlockPlan[])).catch(e=>{
    const msg = formatError(e)
    const status = (e as { response?: { status?: number } })?.response?.status
    if(status===504 || status===500) setError(`${msg} — backend busy, retry or check /health`)
    else setError(msg)
  })
  useEffect(()=>{load()},[])
  useEffect(()=>{
    const h = HORIZONS[mode]
    if(h){
      setHorizonStart(h.start)
      setHorizonEnd(h.end)
    }
    setSelected(null)
    setError('')
  },[mode])
   const generate=async ()=>{
    setError('')
    setLoading(true)
    try{
      const r=await api.post('/api/plans/generate', {horizon_start:horizonStart, horizon_end:horizonEnd, horizon_type:mode})
      await load()
      const newId = (r.data as { plan_id?: string })?.plan_id
      if(newId){
        const pid = newId.toUpperCase()
        try{
          const full = await api.get(`/api/plans/${pid}`)
          setSelected(full.data as typeof selected)
        }catch(e:unknown){
          // fallback to generation response even if view fetch fails (e.g. 504 transient)
          const msg = formatError(e as Error)
          const st = (e as { response?: { status?: number } })?.response?.status
          if(st===504 || st===500){
            setError(`${msg} — view fetch busy, showing generated preview. Click View to retry.`)
          }
          setSelected(r.data as typeof selected)
        }
      }else{
        setSelected(r.data as typeof selected)
      }
    }catch(e:unknown){
      const msg = formatError(e as Error)
      const st = (e as { response?: { status?: number } })?.response?.status
      if(st===504) setError(`${msg} — generate validation busy, backend fallback should have succeeded; please retry.`)
      else setError(msg)
    }
    finally{ setLoading(false)}
  }
  const loadPlan=async (id:string)=>{
    setError('')
    try{
      const pid = (id || '').toUpperCase()
      const r=await api.get(`/api/plans/${pid}`)
      setSelected(r.data)
    }catch(e:unknown){
      const msg = formatError(e as Error)
      const st = (e as { response?: { status?: number } })?.response?.status
      if(st===504) setError(`${msg} — validation timeout (pool busy). Backend now falls back to valid:true; please retry View.`)
      else if(st===500) setError(`${msg} — server error on view, check /health and retry.`)
      else setError(msg)
    }
  }
  const submit=async ()=>{
    if(!selected) return
    const pid = (selected.plan_id || '').toUpperCase()
    if(selected.status !== 'DRAFT'){
      setError(`Only DRAFT can be submitted (current: ${selected.status})`)
      return
    }
    setError('')
    try{
      await api.post(`/api/plans/${pid}/submit-review`)
      await loadPlan(pid)
      await load()
    }catch(e:unknown){
      const msg = formatError(e as Error)
      const st = (e as { response?: { status?: number } })?.response?.status
      if(st===504) setError(`${msg} — submit validation busy; backend fallback is enabled (8s). Please retry.`)
      else setError(msg)
    }
  }
  const approve=async ()=>{
    if(!selected) return
    const pid = (selected.plan_id || '').toUpperCase()
    try{ await api.post(`/api/plans/${pid}/approve`, {approver_id: approveDept.toLowerCase()+'_officer', approver_role: approveDept, reason: `Approved by ${approveDept}`}); await loadPlan(pid); await load()}catch(e:unknown){setError(formatError(e as Error))}
  }
  const reject=async ()=>{
    if(!selected) return
    const pid = (selected.plan_id || '').toUpperCase()
    // TODO: replace window.prompt with dialog component (rb-dialog)
    const reason=window.prompt('Rejection reason? (required)')
    if(!reason) return
    try{ await api.post(`/api/plans/${pid}/reject`, {reason, approver_id:'officer1'}); await loadPlan(pid); await load()}catch(e:unknown){setError(formatError(e as Error))}
  }
  const editBlock=async (blk: Block)=>{
    if(!selected || selected.status!=='DRAFT'){ setError('Approved and published plans are immutable. Create revision.'); return }
    // TODO: replace window.prompt with dialog component (rb-dialog) + date validation
    const newDate=window.prompt('New service_date YYYY-MM-DD', blk.service_date)
    if(!newDate) return
    if(!/^\d{4}-\d{2}-\d{2}$/.test(newDate)){ setError('Invalid date format — use YYYY-MM-DD'); return }
    const pid = (selected.plan_id || '').toUpperCase()
    const bid = (blk.block_id || '').toUpperCase()
    try{ await api.patch(`/api/plans/${pid}/draft-blocks/${bid}`, {service_date:newDate, reason:'Officer editing', editor:'planner1'}); await loadPlan(pid)}catch(e:unknown){setError(formatError(e as Error))}
  }
  const exportCsv=async ()=>{
    if(!selected) return
    const pid = (selected.plan_id || '').toUpperCase()
    try{
      const r=await api.get(`/api/plans/${pid}/export?format=csv`, {responseType:'blob'})
      const url=window.URL.createObjectURL(new Blob([r.data as BlobPart]))
      const a=document.createElement('a'); a.href=url; a.download=`${pid}.csv`; a.click(); window.URL.revokeObjectURL(url)
    }catch(e:unknown){ setError('Export failed: '+formatError(e as Error))}
  }
  const exportPdf=async ()=>{
    if(!selected) return
    const pid = (selected.plan_id || '').toUpperCase()
    try{
      const r=await api.get(`/api/plans/${pid}/export?format=pdf`, {responseType:'blob'})
      const url=window.URL.createObjectURL(new Blob([r.data as BlobPart]))
      const a=document.createElement('a'); a.href=url; a.download=`${pid}.pdf`; a.click(); window.URL.revokeObjectURL(url)
    }catch(e:unknown){ setError('Export failed: '+formatError(e as Error))}
  }
  return <div className="page-wrap">
    <div className="page-header">
      <h1>Planner</h1>
      <div className="page-subtitle">Weekly / Monthly / Daily · Human-Approved Prototype</div>
    </div>
    <PrototypeDisclaimer />
    <div className="rb-card rb-card--accent">
      <h3 className="rb-card-title">Generate</h3>
      <div className="rb-card-desc">Human-Approved Prototype · No data → 400 · Train/Goods hard → no assignment · Solver never auto-publishes</div>
      <div className="rb-form-grid">
        <div className="rb-field">
          <label htmlFor="planner-start">Start</label>
          <input id="planner-start" type="date" className="rb-input" value={horizonStart} onChange={e=>setHorizonStart(e.target.value)} />
        </div>
        <div className="rb-field">
          <label htmlFor="planner-end">End</label>
          <input id="planner-end" type="date" className="rb-input" value={horizonEnd} onChange={e=>setHorizonEnd(e.target.value)} />
        </div>
        <div className="rb-field">
          <label htmlFor="planner-mode">Mode</label>
          <select id="planner-mode" className="rb-select" value={mode} onChange={e=>setMode(e.target.value as keyof typeof HORIZONS)}>
            <option value="WEEKLY">WEEKLY</option>
            <option value="MONTHLY">MONTHLY</option>
            <option value="DAILY">DAILY</option>
          </select>
        </div>
      </div>
      <div style={{display:'flex',alignItems:'center',gap:10,marginTop:12, flexWrap:'wrap'}}>
        <button onClick={generate} disabled={loading} className="btn btn-teal">
          {loading && <span className="spinner" style={{width:14,height:14,borderWidth:2}} aria-hidden />}
          {loading?'Generating…':'★ Generate Plan'}
        </button>
        {loading && <span className="loading-inline" style={{fontSize:11.5}}>CP-SAT · 5s · 8 workers</span>}
      </div>
      {error && <div role="alert" style={{color:'#7a1a1a', background:'#fef2f2', padding:'10px 12px', marginTop:10, border:'1px solid #fecaca', borderRadius:4, fontSize:12.5, lineHeight:1.4, wordBreak:'break-word'}}>{error}</div>}
      <div style={{fontSize:11, color:'var(--text-muted)', marginTop:8, lineHeight:1.4}}>Weekly (2026-09-01→07) → Monthly (→30) → Daily (single day, emergency). No data → 400. Train/Goods hard → no assignment. Solver never auto-publishes; requires human approval.</div>
    </div>
    <Card title="Plans" className="" action={<span className="pill pill--count" style={{fontSize:11}}>{plans.length} total</span>}>
      <div className="rb-card-desc" style={{marginTop:-2}}>Unambiguous Status · Click View to inspect</div>
      {plans.length===0 ? <div className="empty-state">No plans — generate weekly/monthly/daily above.</div> :
      <div className="rb-table-wrap" style={{maxHeight:350}}>
        <table className="rb-table">
          <thead><tr><th>Plan</th><th>Horizon</th><th>Status</th><th>Solver</th><th>Action</th></tr></thead>
          <tbody>{plans.slice(0,20).map((p)=><tr key={p.plan_id} style={{background: p.status==='APPROVED'?'#e3f2fd': p.status==='UNDER_REVIEW'?'#fff3e0':'white'}}><td><span className="mono-pill" style={{fontSize:11}}>{p.plan_id}</span></td><td style={{whiteSpace:'nowrap', fontSize:12}}>{p.horizon_type} {formatDateKolkata(p.start_date)}→{formatDateKolkata(p.end_date)}</td><td><PlanStatus status={p.status} solver={p.solver_status} /></td><td><span className="mono" style={{fontSize:11}}>{p.solver_status}</span></td><td><button onClick={()=>loadPlan(p.plan_id)} className="btn btn-ghost btn-sm">View</button></td></tr>)}</tbody>
        </table>
        {plans.length>20 && <div style={{fontSize:11, color:'var(--text-muted)', padding:'6px 10px', background:'#f8fafb', borderTop:'1px solid #eef2f6'}}>Showing 20 of {plans.length}</div>}
      </div>}
    </Card>
    {selected && <div className="rb-card">
      <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', gap:8, flexWrap:'wrap'}}>
        <h3 className="rb-card-title" style={{display:'flex',alignItems:'center',gap:8, flexWrap:'wrap'}}><span className="mono-pill">{selected.plan_id}</span> <span style={{fontSize:13, color:'var(--text-secondary)', fontWeight:600}}>Plan Detail</span></h3>
        <PlanStatus status={selected.status} solver={selected.solver_status} />
      </div>
      <div style={{display:'flex', gap:6, alignItems:'center', flexWrap:'wrap', marginTop:8, fontSize:12, color:'var(--text-secondary)'}}>
        <span>Blocks: <strong style={{color:'var(--text-primary)'}}>{selected.blocks?.length ?? 0}</strong></span>
        <span style={{color:'#d0d8e4'}}>•</span>
        <span>Integrated: <strong style={{color:'var(--text-primary)'}}>{selected.blocks?.filter((b)=> (b.tasks?.length ?? 0) >1).length ?? 0}</strong></span>
        <span style={{color:'#d0d8e4'}}>•</span>
        <span>Solver: <span className="mono-pill" style={{fontSize:10.5}}>{selected.solver_status}</span> → <span className="pill pill--muted" style={{fontSize:10.5}}>{selected.status}</span></span>
      </div>
      {selected.required_departments && <div style={{marginTop:10, background:'#f8fafb', padding:'10px 12px', borderRadius:4, border:'1px solid #eef2f6'}}>
        <div style={{display:'flex', gap:6, flexWrap:'wrap', alignItems:'center', fontSize:12}}>
          <span style={{fontSize:10.5, fontWeight:700, letterSpacing:0.4, textTransform:'uppercase', color:'var(--text-secondary)'}}>Required:</span>
          {selected.required_departments.length ? selected.required_departments.map(d=><span key={d} className="pill pill--muted" style={{fontSize:11}}>{d}</span>) : <span style={{fontSize:11, color:'var(--text-muted)'}}>—</span>}
        </div>
        <div style={{display:'flex', gap:6, flexWrap:'wrap', alignItems:'center', fontSize:12, marginTop:6}}>
          <span style={{fontSize:10.5, fontWeight:700, letterSpacing:0.4, textTransform:'uppercase', color:'var(--text-secondary)'}}>Approved:</span>
          {selected.approved_departments?.length ? selected.approved_departments.map(d=><span key={d} className="pill pill--blue" style={{fontSize:11}}>{d} ✓</span>) : <span className="pill pill--muted" style={{fontSize:11}}>none</span>}
          <span style={{fontSize:10.5, fontWeight:700, letterSpacing:0.4, textTransform:'uppercase', color:'var(--text-secondary)', marginLeft:8}}>Pending:</span>
          {selected.pending_departments?.length ? selected.pending_departments.map(d=><span key={d} className="pill pill--amber" style={{fontSize:11}}>{d}</span>) : <span className="pill pill--green" style={{fontSize:11}}>— all approved</span>}
        </div>
        {selected.approvals && selected.approvals.length>0 && <div style={{marginTop:8, display:'flex', gap:4, flexWrap:'wrap'}}>{selected.approvals.map((a)=><span key={a.approver_role} className="pill pill--blue" style={{fontSize:11}}>{a.approver_role} ✓ {a.approver_id}</span>)}</div>}
      </div>}
      <div style={{marginTop:10}}>
        <div style={{fontSize:10.5, fontWeight:700, letterSpacing:0.4, textTransform:'uppercase', color:'var(--text-secondary)', marginBottom:4}}>Objective</div>
        <pre className="mono" style={{background:'#f8fafb', padding:10, fontSize:11, whiteSpace:'pre-wrap', wordBreak:'break-word', border:'1px solid #eef2f6', borderRadius:4, margin:0, maxHeight:160, overflow:'auto'}}>{JSON.stringify(selected.objective_breakdown,null,2)}</pre>
      </div>
      <div className="metric-row" style={{marginTop:8}}>
        <span className="metric-pill" style={{display:'inline-flex', gap:6, alignItems:'center'}}>Baseline <span className="mono" style={{fontWeight:800, color:'var(--chart-navy)'}}>{JSON.stringify(selected.baseline_metrics)}</span></span>
        <span className="metric-pill" style={{display:'inline-flex', gap:6, alignItems:'center'}}>Optimized <span className="mono" style={{fontWeight:800, color:'var(--teal)'}}>{JSON.stringify(selected.optimized_metrics)}</span></span>
      </div>
      <div style={{marginTop:8}}>
        <ValidationPanel validation={selected.validation as import('../types').ValidationResult | null | undefined} />
      </div>
      <details style={{marginTop:8, background:'#fff8e1', border:'1px solid #ffecb3', borderRadius:4, padding:'8px 10px'}}>
        <summary style={{fontSize:12, fontWeight:700, cursor:'pointer', color:'#7a4a00'}}>Unscheduled reasons ({Array.isArray(selected.unscheduled_reasons) ? (selected.unscheduled_reasons as unknown[]).length : 0})</summary>
        <pre className="mono" style={{fontSize:11, maxHeight:160, overflow:'auto', background:'white', padding:8, border:'1px solid #ffe0b2', borderRadius:4, marginTop:8, whiteSpace:'pre-wrap', wordBreak:'break-word'}}>{JSON.stringify(selected.unscheduled_reasons,null,2)}</pre>
      </details>
      <div style={{marginTop:10}}>
        <Gantt blocks={(selected.blocks ?? []) as import('../types').Block[]} />
      </div>
      <div style={{marginTop:12, display:'flex', gap:8, flexWrap:'wrap', alignItems:'center'}}>
        {selected.status==='DRAFT' && <><button onClick={submit} className="btn btn-amber">② Submit for Review</button> <button onClick={()=>selected.blocks?.[0] && editBlock(selected.blocks[0] as Block)} disabled={!selected.blocks?.length} className="btn btn-ghost btn-sm">Edit Draft (test)</button></>}
        {selected.status==='UNDER_REVIEW' && <>
          <span style={{fontSize:12, fontWeight:600, color:'var(--text-primary)'}}>Approvals by every department:</span>
          <select value={approveDept} onChange={e=>setApproveDept(e.target.value)} className="rb-select" style={{height:32, fontSize:12}}>{(['CONTROL_OFFICE','ADMIN'] as const).map(r=> <option key={r} value={r}>{r}</option>)}</select>
          <button onClick={approve} className="btn btn-blue">Approve as {approveDept}</button>
          <button onClick={reject} className="btn btn-ghost">Reject</button>
          {selected.pending_departments && selected.pending_departments.length>0 && <span style={{fontSize:11, color:'#e65100'}}>Pending: {selected.pending_departments.join(', ')} → each dept must approve, or CONTROL_OFFICE final approves all</span>}
        </>}
        {selected.status==='APPROVED' && <span className="pill pill--blue" style={{padding:'6px 10px', borderRadius:4, fontSize:12, fontWeight:600}}>✓ Approved — immutable; use Revision to edit. Go to Execution to complete tasks per department.</span>}
        {selected.status!=='DRAFT' && selected.status!=='APPROVED' && selected.status!=='UNDER_REVIEW' && <span style={{fontSize:11, color:'var(--text-muted)'}}>Status: {selected.status}</span>}
        {selected.status!=='DRAFT' && selected.status!=='APPROVED' && <span style={{fontSize:11, color: selected.status==='DRAFT' ? 'transparent' : 'var(--text-muted)'}}>{selected.status!=='DRAFT' ? 'Edit hidden for non-DRAFT (immutable rule).' : ''}</span>}
        {selected.status==='APPROVED' && <span style={{fontSize:11, color:'var(--text-muted)'}}>Edit hidden for non-DRAFT (immutable rule).</span>}
        <div style={{display:'flex', gap:6, marginLeft:'auto'}}>
          <button onClick={exportCsv} className="btn btn-ghost btn-sm">Export CSV</button>
          <button onClick={exportPdf} className="btn btn-ghost btn-sm">Export PDF</button>
        </div>
      </div>
      {(selected.blocks?.length ?? 0)===0 ? <div className="empty-state" style={{marginTop:10}}>No blocks — no feasible windows or all tasks filtered by safety/deadline.</div> :
      <div style={{display:'flex', flexDirection:'column', gap:8, marginTop:10}}>
      {(selected.blocks ?? []).map((b)=><div key={b.block_id} className="rb-card rb-card--dense" style={{margin:0, borderLeft:`3px solid ${(b.tasks?.length ?? 0)>1 ? 'var(--teal)' : '#e0e6ed'}`}}>
        <div style={{display:'flex', gap:6, flexWrap:'wrap', alignItems:'center'}}>
          <span className="mono-pill">{b.block_id}</span>
          <span className="pill pill--blue" style={{fontSize:11}}>{b.corridor_id}{b.section_id ? ` · ${b.section_id}` : ''}{b.line_id ? ` · ${b.line_id}` : ''}</span>
          <PlanStatus status={b.status ?? 'UNKNOWN'} />
          {(b.tasks?.length ?? 0)>1 && <span className="pill pill--green" style={{fontSize:11}}>Integrated {b.tasks?.length}</span>}
          {b.status==='COMPLETED' && <span className="pill pill--amber" style={{fontSize:11}}>🔒 Locked — Completed</span>}
        </div>
        <div style={{display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(180px, 1fr))', gap:6, marginTop:8, fontSize:12, color:'var(--text-secondary)'}}>
          <span>Date <strong style={{color:'var(--text-primary)'}}>{formatDateKolkata(b.service_date)}</strong></span>
          <span>Time <strong className="mono" style={{color:'var(--text-primary)'}}>{minutesToTime(b.start_time)}–{minutesToTime(b.end_time)}</strong></span>
          <span>Dept <span className="pill pill--muted" style={{fontSize:11}}>{b.department||'—'}</span></span>
        </div>
        <div style={{fontSize:11, color:'var(--text-secondary)', marginTop:6, lineHeight:1.4}}>
          Tasks: <span className="mono" style={{fontSize:11, background:'#f8fafb', padding:'2px 6px', borderRadius:4, border:'1px solid #eef2f6', wordBreak:'break-word'}}>{(b.tasks||[]).map((t: unknown)=>{
            if(t == null) return ''
            if(typeof t === 'string') return t
            const o = t as { task_id?: string; id?: string; department?: string; status?: string }
            const id = o.task_id || o.id || ''
            if(!id) return ''
            return `${id}${o.department ? ` (${o.department})` : ''}${o.status ? ` ${o.status}` : ''}`
          }).filter(Boolean).join(', ') || '—'}</span>
        </div>
        {selected.status==='DRAFT' ? <button onClick={()=>editBlock(b as Block)} className="btn btn-ghost btn-sm" style={{marginTop:8}}>Edit block date</button> : <span style={{marginLeft:0, fontSize:11, color:'var(--text-muted)', marginTop:6, display:'inline-block'}}>(immutable)</span>}
      </div>)}
      </div>}
    </div>}
  </div>
}
