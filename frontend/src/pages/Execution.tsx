import { useEffect, useState, useCallback } from 'react'
import api from '../services/api'
import Card from '../components/Card'
import { formatError } from '../services/errors'
import { PrototypeDisclaimer } from '../components/WarningBanner'
import { DEPARTMENTS } from '../constants/departments'
import { minutesToTime } from '../services/formatters'
import type { BlockPlan, Block } from '../types'

export default function Execution(){
  const [plans, setPlans]=useState<BlockPlan[]>([])
  const [selectedPlan, setSelectedPlan]=useState('')
  const [blocks, setBlocks]=useState<Block[]>([])
  const [planStatus, setPlanStatus]=useState('')
  const [msg, setMsg]=useState('')
  const [err, setErr]=useState('')
  const [dept, setDept]=useState<string>(()=> localStorage.getItem('department')||'ENGINEERING')
  useEffect(()=>{api.get('/api/plans').then(r=>setPlans(r.data as BlockPlan[]))},[])
  const loadBlocks=useCallback(async ()=>{
    if(!selectedPlan) return
    const r=await api.get(`/api/plans/${selectedPlan}`)
    const data = r.data as { blocks: Block[]; status: string }
    setBlocks(data.blocks)
    setPlanStatus(data.status)
  }, [selectedPlan])
  const handleDeptChange=(v:string)=>{
    setDept(v)
    try{
      localStorage.setItem('department', v)
      window.dispatchEvent(new Event('rb_department_change'))
    }catch{}
  }
  const execute=async (blk: Block, mode:'COMPLETED'|'PARTIALLY_COMPLETED'|'CANCELLED')=>{
    setErr(''); setMsg('')
    try{
      const allTasks = (blk.tasks||[]).map((t)=> t.task_id)
      const deptTasks = (blk.tasks||[]).filter((t)=> (t.department||'').toUpperCase()===dept.toUpperCase()).map((t)=>t.task_id)
      const targetTasks = deptTasks.length ? deptTasks : allTasks
      const payload={
        actual_start: blk.start_time,
        actual_end: blk.end_time+10,
        service_date: blk.service_date,
        recorded_by: dept.toLowerCase()+'_engineer',
        notes: `${mode} by ${dept}`,
        status: mode,
        completed_task_ids: mode==='COMPLETED' ? targetTasks : [],
        partially_completed_task_ids: mode==='PARTIALLY_COMPLETED' ? targetTasks : [],
        cancelled_task_ids: mode==='CANCELLED' ? targetTasks : [],
        reason: mode!=='COMPLETED' ? `Marked ${mode} by ${dept}` : ''
      }
      const r=await api.post(`/api/blocks/${blk.block_id}/execution`, payload)
      const data = r.data as { execution_id?:string; id?:string; code?: number }
      setMsg(`✓ ${dept}: ${mode} recorded ${data.execution_id || data.id||''} for ${blk.block_id} (${targetTasks.length} tasks) code ${data.code || 200}`)
      loadBlocks()
    }catch(e:unknown){ setErr(formatError(e))}
  }

  const doTestInvalid=async ()=>{
    setErr('')
    const target = blocks[0]?.block_id || 'BLK-TEST0001'
    try{ await api.post(`/api/blocks/${target}/execution`, {actual_start:10, actual_end:5, status:'COMPLETED', completed_task_ids:[], recorded_by:'x'} )}catch(e:unknown){setErr('Validation: '+formatError(e))}
  }
  const doTestWnd=async ()=>{
    setErr('')
    try{ await api.post(`/api/blocks/WND-TEST1234/execution`, {actual_start:60, actual_end:120, status:'COMPLETED', completed_task_ids:[], recorded_by:'x'} )}catch(e:unknown){setErr('WND rejection → '+formatError(e))}
  }

  const filtered = blocks.filter((b)=>{
    if(!dept) return true
    if(dept==='CONTROL_OFFICE' || dept==='ADMIN') return true
    const hasDept = (b.tasks||[]).some((t)=> (t.department||'').toUpperCase()===dept.toUpperCase())
    if(b.department && b.department.toUpperCase().includes(dept.toUpperCase())) return true
    return hasDept
  })

  const statusBg = planStatus==='APPROVED' ? '#e3f2fd' : planStatus==='COMPLETED' ? '#e8f5e9' : planStatus==='PUBLISHED' ? '#e3f2fd' : '#fff3e0'
  const statusColor = planStatus==='APPROVED' ? '#0d47a1' : planStatus==='COMPLETED' ? '#1b5e20' : '#7a3e00'
  const statusBorder = planStatus==='APPROVED' ? '#bbdefb' : planStatus==='COMPLETED' ? '#c8e6c9' : '#ffe0b2'

  return <div className="page-wrap">
    <div className="page-header">
      <h1>Execution</h1>
      <div className="page-subtitle">Complete by department · idempotent</div>
    </div>
    <PrototypeDisclaimer />

    <div className="filter-bar">
      <div className="rb-field" style={{minWidth:280, flex:1}}>
        <label htmlFor="exec-plan">Plan</label>
        <select id="exec-plan" className="rb-select" value={selectedPlan} onChange={e=>setSelectedPlan(e.target.value)} style={{minWidth:280}}>
          <option value="">Select Plan (APPROVED required)</option>
          {plans.map((p)=><option key={p.plan_id} value={p.plan_id}>{p.plan_id} - {p.status} ({p.horizon_type})</option>)}
        </select>
      </div>
      <button onClick={loadBlocks} className="btn btn-teal" style={{alignSelf:'flex-end'}}>Load Blocks</button>
      <div className="rb-field">
        <label htmlFor="exec-dept">My Dept</label>
        <select id="exec-dept" className="rb-select" value={dept} onChange={e=>handleDeptChange(e.target.value)}>
          {DEPARTMENTS.filter(d=>['ENGINEERING','S_AND_T','TRACTION','PROJECTS','CONTROL_OFFICE','ADMIN'].includes(d)).map(d=> <option key={d} value={d}>{d}</option>)}
        </select>
      </div>
      {planStatus && <span className="pill" style={{background: statusBg, color: statusColor, borderColor: statusBorder, alignSelf:'flex-end', padding:'6px 10px', fontSize:11, fontWeight:700}}>Plan: {planStatus} {planStatus!=='APPROVED' && planStatus!=='PUBLISHED' && '(must be APPROVED to execute reliably)'}</span>}
    </div>

    {err && <div role="alert" style={{color:'#7a1a1a', background:'#ffebee', padding:'10px 12px', marginTop:10, border:'1px solid #ffcdd2', borderRadius:4, fontSize:12.5, lineHeight:1.4}}>{err}</div>}
    {msg && <div role="alert" style={{color:'#1b5e20', background:'#e8f5e9', padding:'10px 12px', marginTop:10, border:'1px solid #c8e6c9', borderRadius:4, fontSize:12.5, lineHeight:1.4}}>{msg}</div>}

    <div style={{fontSize:11, color:'var(--text-muted)', marginTop:8, lineHeight:1.4}}>① Select APPROVED plan → ② Select your department → ③ See <b style={{color:'var(--text-secondary)'}}>only your tasks</b> (integrated context visible) → ④ Record COMPLETED / PARTIALLY / CANCELLED. Each department completes <b style={{color:'var(--text-secondary)'}}>its own tasks</b> in its blocks. Duplicate submission → 409 or idempotent. Completed → 🔒 locked, immutable. Historical execution feeds next plan's priority.</div>

    {filtered.length===0 && blocks.length>0 && <div className="empty-state" style={{marginTop:12}}>No blocks for {dept} — switch to CONTROL_OFFICE to see all, or generate a plan with {dept} tasks.</div>}

    {filtered.map((b)=>{
      const isCompleted = b.status==='COMPLETED'
      const statusPill = isCompleted ? 'pill--green' : b.status==='CANCELLED' ? 'pill--red' : 'pill--blue'
      return (
        <Card key={b.block_id} title="" className="rb-card--dense" style={{margin:'12px 0'}}>
          <div style={{display:'flex', gap:6, flexWrap:'wrap', alignItems:'center'}}>
            <span className="mono-pill">{b.block_id}</span>
            <span className="mono" style={{fontSize:11, background:'#f8fafb', padding:'4px 6px', borderRadius:4, border:'1px solid #eef2f6', fontWeight:600}}>{b.service_date}</span>
            <span className="mono" style={{fontSize:11, background:'#f8fafb', padding:'4px 6px', borderRadius:4, border:'1px solid #eef2f6', fontWeight:600}}>{minutesToTime(b.start_time)}–{minutesToTime(b.end_time)}</span>
            <span className="pill pill--blue" style={{fontSize:11}}>{b.corridor_id}</span>
            {b.line_id && <span className="mono-pill" style={{fontSize:11}}>{b.line_id}</span>}
            {b.department && <span className="pill pill--muted" style={{fontSize:11}}>{b.department}</span>}
            <span className={`pill ${statusPill}`} style={{fontSize:11}}>{b.status || '—'}</span>
            {isCompleted && <span className="pill pill--amber" style={{fontSize:11}}>🔒 Locked</span>}
          </div>
          <div className="mono" style={{fontSize:11, color:'var(--text-secondary)', marginTop:8, lineHeight:1.4, wordBreak:'break-word', background:'#f8fafb', padding:'6px 8px', borderRadius:4, border:'1px solid #eef2f6'}}>
            Tasks ({(b.tasks||[]).length}): {(b.tasks||[]).map((t)=> `${t.task_id} (${t.department||b.department||''})=${t.status||''}`).join(', ') || '—'}
          </div>
          <div style={{marginTop:10, display:'flex', gap:6, flexWrap:'wrap'}}>
            <button onClick={()=>execute(b,'COMPLETED')} disabled={isCompleted} className="btn btn-green btn-sm">✓ Record COMPLETED ({dept})</button>
            <button onClick={()=>execute(b,'PARTIALLY_COMPLETED')} disabled={isCompleted} className="btn btn-amber btn-sm">◐ Partially Completed</button>
            <button onClick={()=>execute(b,'CANCELLED')} disabled={isCompleted} className="btn btn-red btn-sm">✕ Cancelled (requires reason)</button>
          </div>
          {isCompleted && <div style={{fontSize:11, color:'#2e7d32', marginTop:6, background:'#e8f5e9', padding:'6px 8px', borderRadius:4, border:'1px solid #c8e6c9'}}>🔒 This block is locked — duplicate execution returns 409 or idempotent (same payload).</div>}
        </Card>
      )
    })}

    {blocks.length===0 && selectedPlan && <div className="empty-state" style={{marginTop:12}}>No blocks — load failed or plan has no blocks.</div>}

    <Card title="Execution Rules (Unambiguous)">
      <ul style={{fontSize:11, color:'var(--text-secondary)', lineHeight:1.6, margin:'6px 0 0 16px', padding:0}}>
        <li><b style={{color:'var(--text-primary)'}}>Actual end must be ≥ start</b> → 400 else</li>
        <li><b style={{color:'var(--text-primary)'}}>Cancelled/Deferred requires reason</b> → 400 else</li>
        <li><b style={{color:'var(--text-primary)'}}>Task must belong to block</b> → 400 else</li>
        <li><b style={{color:'var(--text-primary)'}}>Never use WND-* where BLK-* required</b> → 400</li>
        <li><b style={{color:'var(--text-primary)'}}>Duplicate execution</b> → 409 (or idempotent if same payload)</li>
        <li><b style={{color:'var(--text-primary)'}}>Completed → locked</b>, preserved across revisions/replans</li>
      </ul>
      <div style={{display:'flex', gap:6, flexWrap:'wrap', marginTop:12, paddingTop:10, borderTop:'1px solid #eef2f6'}}>
        <button onClick={doTestInvalid} className="btn btn-ghost btn-sm">Test Invalid (end&lt;start → 400)</button>
        <button onClick={doTestWnd} className="btn btn-ghost btn-sm">Test WND rejection (400)</button>
      </div>
    </Card>
  </div>
}
