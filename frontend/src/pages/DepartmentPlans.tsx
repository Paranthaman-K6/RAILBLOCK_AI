import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import api from '../services/api'
import Card from '../components/Card'
import Gantt from '../components/Gantt'
import PlanStatus from '../components/PlanStatus'
import { DEPARTMENTS } from '../constants/departments'
import { formatError } from '../services/errors'
import type { BlockPlan, Block } from '../types'

interface DeptView {
  plan_id: string
  department: string
  plan_status: string
  my_blocks: Block[]
  integrated_blocks: Block[]
}

interface NotificationItem {
  id?: string | number
  message?: string
  title?: string
  body?: string
  text?: string
  created_at?: string
  date?: string
  timestamp?: string
  type?: string
  [k: string]: unknown
}

export default function DepartmentPlans(){
  const [dept, setDept]=useState<string>(()=> localStorage.getItem('department')||'ENGINEERING')
  const [plans, setPlans]=useState<BlockPlan[]>([])
  const [view, setView]=useState<DeptView | null>(null)
  const [notifications, setNotifications]=useState<NotificationItem[]>([])
  const [notifError, setNotifError]=useState('')
  const [notifLoading, setNotifLoading]=useState(false)
  const [plansError, setPlansError]=useState('')
  const [viewError, setViewError]=useState('')

  const load=useCallback(()=>{
    setPlansError('')
    return api.get('/api/approved-plans', {params:{department:dept}}).then(r=>setPlans(r.data as BlockPlan[])).catch((e: unknown)=> setPlansError(formatError(e as never)))
  }, [dept])

  useEffect(()=>{load()},[load])

  const handleDeptChange=(v:string)=>{
    setDept(v)
    try{
      localStorage.setItem('department', v)
      window.dispatchEvent(new Event('rb_department_change'))
      window.dispatchEvent(new StorageEvent('storage', { key:'department', newValue: v } as unknown as StorageEventInit))
    }catch{}
  }

  const openView=async (planId:string)=>{
    setViewError('')
    try{
      const r=await api.get(`/api/plans/${planId}/department-view`, {params:{department:dept}})
      setView(r.data as DeptView)
    }catch(e: unknown){
      setViewError(formatError(e as never))
      setView(null)
    }
  }

  const fetchNotifications=async ()=>{
    setNotifLoading(true); setNotifError('')
    try{
      const r=await api.get('/api/notifications', {params:{department:dept}})
      const data = r.data as NotificationItem[] | { notifications?: NotificationItem[]; items?: NotificationItem[] }
      const list: NotificationItem[] = Array.isArray(data) ? data : (data.notifications || data.items || [])
      setNotifications(list)
    }catch(e: unknown){
      setNotifError(formatError(e as never))
    }finally{ setNotifLoading(false)}
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(()=>{ fetchNotifications() }, [dept])

  return <div className="page-wrap">
    <div className="page-header">
      <h1>Department Plans</h1>
      <div className="page-subtitle">Approved views · my vs integrated</div>
    </div>

    <div className="filter-bar">
      <div className="rb-field">
        <label htmlFor="dp-dept">Department</label>
        <select id="dp-dept" className="rb-select" value={dept} onChange={e=>handleDeptChange(e.target.value)}>
          {DEPARTMENTS.map(d=> <option key={d} value={d}>{d}</option>)}
        </select>
      </div>
      <button onClick={load} className="btn btn-ghost" style={{alignSelf:'flex-end'}}>Load Approved</button>
      <span className="pill pill--count" style={{marginLeft:'auto', alignSelf:'flex-end'}}>{plans.length} approved</span>
    </div>

    {plansError && <div role="alert" style={{color:'#7a1a1a', background:'#ffebee', padding:'10px 12px', marginTop:10, border:'1px solid #ffcdd2', borderRadius:4, fontSize:12.5}}>{plansError}</div>}

    <Card title="Approved Plans" action={<span className="pill pill--count" style={{fontSize:11}}>{plans.length} plans</span>}>
      {plans.length===0? <div className="empty-state">No approved plans <div style={{marginTop:10}}><Link to="/planner" className="btn btn-teal btn-sm">Go to Planner</Link></div></div> : <div className="rb-table-wrap"><table className="rb-table"><thead><tr><th>Plan</th><th>Status</th><th>Action</th></tr></thead><tbody>{plans.map((p)=><tr key={p.plan_id}><td><span className="mono-pill" style={{fontSize:11}}>{p.plan_id}</span></td><td><PlanStatus status={p.status} /></td><td><button onClick={()=>openView(p.plan_id)} className="btn btn-ghost btn-sm">View</button></td></tr>)}</tbody></table></div>}
    </Card>

    {viewError && <div role="alert" style={{color:'#7a1a1a', background:'#ffebee', padding:'10px 12px', marginTop:10, border:'1px solid #ffcdd2', borderRadius:4, fontSize:12.5}}>{viewError}</div>}
    {view && <Card title="" className="" action={<span className="pill pill--count" style={{fontSize:11}}>{view.department}</span>}>
      <div style={{display:'flex', gap:8, alignItems:'center', flexWrap:'wrap', marginBottom:8}}>
        <span className="mono-pill">{view.plan_id}</span>
        <PlanStatus status={view.plan_status} />
        <span className="pill pill--count" style={{fontSize:11}}>{view.department}</span>
      </div>

      <div style={{marginTop:14}}>
        <h4 style={{margin:'0 0 6px 0', display:'flex', alignItems:'center', gap:8, fontSize:13, fontWeight:700}}>My Tasks <span className="pill" style={{background:'#e6f5f5', color:'#0f5a5a', borderColor:'#c2e8e8', fontSize:11}}>{view.my_blocks.length}</span></h4>
        <Gantt blocks={view.my_blocks} />
      </div>

      <div style={{marginTop:16}}>
        <h4 style={{margin:'0 0 6px 0', display:'flex', alignItems:'center', gap:8, fontSize:13, fontWeight:700}}>Integrated Cross-Department Context <span className="pill pill--muted" style={{fontSize:11}}>{view.integrated_blocks.length}</span></h4>
        <Gantt blocks={view.integrated_blocks} />
        <div className="pill" style={{background:'#e3f2fd', color:'#0d47a1', borderColor:'#bbdefb', marginTop:8, display:'inline-flex', padding:'6px 10px', borderRadius:4, fontSize:12, fontWeight:600, whiteSpace:'normal', lineHeight:1.3}}>Other departments’ work visible as coordination context. No unrelated confidential data.</div>
      </div>
    </Card>}

    <Card title="Notifications" action={<span className="pill pill--count" style={{fontSize:11}}>{notifications.length}</span>}>
      <div style={{display:'flex', gap:8, alignItems:'center', marginBottom:10, flexWrap:'wrap'}}>
        <button onClick={fetchNotifications} className="btn btn-ghost btn-sm">Fetch Notifications</button>
        {notifLoading && <span className="loading-inline"><span className="spinner" /> Loading…</span>}
      </div>
      {notifError && <div role="alert" style={{color:'#7a1a1a', background:'#ffebee', padding:'8px 10px', border:'1px solid #ffcdd2', borderRadius:4, fontSize:12, marginBottom:8}}>{notifError}</div>}
      {notifications.length===0 ? <div className="empty-state">{notifLoading ? 'Fetching…' : 'No notifications — all clear for ' + dept}</div> :
        <div style={{display:'flex', flexDirection:'column', gap:6}}>
          {notifications.map((n, idx)=>{
            const msg = (n.message || n.title || n.body || n.text || JSON.stringify(n)) as string
            const date = (n.created_at || n.date || n.timestamp || '') as string
            return (
              <div key={(n.id as string) || idx} style={{display:'flex', gap:8, alignItems:'center', padding:'8px 10px', background:'#f8fafb', border:'1px solid #eef2f6', borderRadius:4, flexWrap:'wrap'}}>
                <span className="mono" style={{fontSize:11, color:'var(--text-muted)', fontWeight:600, whiteSpace:'nowrap'}}>{date ? String(date).slice(0,19).replace('T',' ') : `#${idx+1}`}</span>
                <span className="pill" style={{background:'white', borderColor:'#e0e6ed', color:'var(--text-primary)', fontSize:12, fontWeight:500, whiteSpace:'normal', lineHeight:1.3}}>{msg}</span>
              </div>
            )
          })}
        </div>
      }
    </Card>
  </div>
}
