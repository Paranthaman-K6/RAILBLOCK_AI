import { useEffect, useState, useMemo, useCallback } from 'react'
import api from '../services/api'
import Card from '../components/Card'
import MetricsChart from '../components/MetricsChart'
import PlanStatus from '../components/PlanStatus'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell, CartesianGrid } from 'recharts'
import { PrototypeDisclaimer } from '../components/WarningBanner'
import { formatError } from '../services/errors'
import type { BlockPlan, MetricsData } from '../types'

const PIE_COLORS = ['#4caf50', '#e0e6ed']

export default function Metrics(){
  const [plans, setPlans]=useState<BlockPlan[]>([])
  const [selected, setSelected]=useState<MetricsData | null>(null)
  const [loading, setLoading]=useState(false)
  const [error, setError]=useState('')

  const load=useCallback(()=> api.get('/api/plans').then(r=>setPlans(r.data as BlockPlan[])).catch(e=>setError(formatError(e))), [])
  useEffect(()=>{load()},[load])

  const loadMetrics=useCallback(async (id:string)=>{
    setLoading(true); setError('')
    try{
      const r=await api.get(`/api/metrics/${id}`)
      setSelected(r.data as MetricsData)
    }catch(e:unknown){ setError(formatError(e)) }
    finally{ setLoading(false)}
  }, [])

  const assetChartData = useMemo(()=>{
    if(!selected?.asset_metrics) return []
    return Object.entries(selected.asset_metrics).slice(0,6).map(([aid, m])=>({ name: aid, downtime: (m as {downtime_minutes:number}).downtime_minutes, available: (m as {available_minutes:number}).available_minutes }))
  }, [selected])

  const completionData = useMemo(()=>{
    if(!selected) return []
    const rate = (selected as MetricsData).maintenance_completion_rate || 0
    return [
      { name: 'Completed', value: rate },
      { name: 'Pending', value: 100 - rate },
    ]
  }, [selected])

  const plannedActualData = useMemo(()=>{
    if(!selected?.planned_vs_actual?.length) return [{ name: 'Planned', planned: (selected as MetricsData)?.planned_duration_minutes||0, actual: (selected as MetricsData)?.actual_duration_minutes||0, variance: (selected as MetricsData)?.duration_variance_minutes||0 }]
    return (selected.planned_vs_actual as {block_id:string; planned:number; actual:number; delta:number}[]).slice(0,8).map((p)=>({ name: p.block_id.slice(0,8), planned: p.planned, actual: p.actual, variance: p.delta }))
  }, [selected])

  return <div className="page-wrap">
    <div className="page-header">
      <h1>Metrics</h1>
      <div className="page-subtitle">Baseline vs Optimized · From DB</div>
    </div>
    <PrototypeDisclaimer />
    <div style={{fontSize:11, color:'var(--text-muted)', marginBottom:10, lineHeight:1.4}}>Formulas: asset_downtime = Σ actual (if executed) else planned per asset per block (no double-count) • asset_available = horizon - downtime • availability_pct = 100*available/horizon • completion_rate = completed/scheduled*100 • variance = actual - planned. All from DB state.</div>

    <Card title="Select Plan (Weekly/Monthly/Daily)">
      <div style={{display:'flex', gap:6, flexWrap:'nowrap', overflowX:'auto', paddingBottom:4, scrollbarWidth:'thin'}}>
        {plans.length===0 ? <div className="empty-state" style={{flex:1}}>No plans — generate in Planner</div> :
          plans.slice(0,20).map((p)=>{
            const active = selected?.plan_id===p.plan_id
            return (
              <button key={p.plan_id} onClick={()=>loadMetrics(p.plan_id)} className={`btn btn-sm ${active?'btn-blue':'btn-ghost'}`} style={{flexShrink:0, display:'inline-flex', alignItems:'center', gap:6}}>
                <span className="mono" style={{fontSize:11, fontWeight:700}}>{p.plan_id}</span>
                <PlanStatus status={p.status} />
                <span style={{fontSize:11, opacity:0.85}}>({p.horizon_type})</span>
              </button>
            )
          })
        }
      </div>
      {plans.length>20 && <div style={{fontSize:11, color:'var(--text-muted)', marginTop:6}}>Showing 20 of {plans.length}</div>}
    </Card>

    {loading && <div style={{display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(280px, 1fr))', gap:12, marginTop:12}}>
      {[0,1,2].map(i=> <div key={i} className="rb-card"><div className="skeleton" style={{height:14, width:'40%', marginBottom:10}} /><div className="skeleton skeleton-line" /><div className="skeleton skeleton-line" style={{width:'80%'}} /><div className="skeleton skeleton-line" style={{width:'60%'}} /></div>)}
    </div>}
    {error && <div role="alert" style={{background:'#ffebee', padding:'10px 12px', border:'1px solid #ffcdd2', color:'#7a1a1a', marginTop:10, borderRadius:4, fontSize:12.5}}>{error}</div>}

    {selected && <div>
      <div style={{display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(280px, 1fr))', gap:12, marginTop:12}}>
        <Card title="Blocks & Tasks">
          <div className="metric-row">
            <span className="metric-pill">Blocks <strong style={{color:'var(--chart-navy)'}}>{selected.blocks}</strong> <span style={{color:'var(--text-muted)', fontWeight:500}}>Baseline {(selected.baseline as Record<string,number>)?.blocks ?? (selected.baseline_metrics as Record<string,number>)?.blocks ?? '—'}</span> → <span style={{color:'var(--teal)'}}>Opt {(selected.optimized as Record<string,number>)?.blocks ?? selected.blocks}</span> {(selected.improvement as Record<string,number>)?.blocks_reduced ? <span style={{color:'#4caf50'}}>↓{(selected.improvement as Record<string,number>).blocks_reduced}</span> : ''}</span>
            <span className="metric-pill">Scheduled <strong style={{color:'var(--text-primary)'}}>{selected.scheduled_tasks}</strong> <span style={{color:'var(--text-muted)', fontWeight:500}}>Base {(selected.baseline as Record<string,number>)?.tasks_scheduled ?? '—'}</span> → {(selected.optimized as Record<string,number>)?.tasks_scheduled ?? selected.scheduled_tasks} {(selected.improvement as Record<string,number>)?.tasks_added ? <span style={{color:'#4caf50'}}>+{(selected.improvement as Record<string,number>).tasks_added}</span> : ''}</span>
            <span className="metric-pill">Critical <strong style={{color:'#f44336'}}>{selected.critical_tasks}</strong></span>
            <span className="metric-pill">Integrated <strong style={{color:'var(--teal)'}}>{selected.integrated_groups}</strong></span>
            <span className="metric-pill">Conflicts <strong style={{color: (selected.conflicts as number) >0 ? '#f44336' : 'var(--text-primary)'}}>{selected.conflicts}</strong></span>
            <span className="metric-pill">Unused <strong>{selected.unused_time}m</strong></span>
            <span className="metric-pill">Res Util <strong>{selected.resource_utilization}%</strong></span>
          </div>
          <div style={{marginTop:8}}><span className="pill pill--muted" style={{fontSize:11}}>Dataset: {selected.dataset} • {selected.plan_id}</span></div>
        </Card>

        <Card title="Asset Downtime & Availability (Explicit)">
          <div className="metric-row">
            <span className="metric-pill">Downtime <strong>{selected.asset_downtime_minutes}m</strong></span>
            <span className="metric-pill">Available <strong>{selected.asset_available_minutes}m</strong></span>
            <span className="metric-pill" style={{background: (selected.asset_availability_pct ?? 0) >80 ? '#e8f5e9' : '#fff8e1', borderColor: (selected.asset_availability_pct ?? 0) >80 ? '#c8e6c9' : '#ffecb3', color: (selected.asset_availability_pct ?? 0) >80 ? '#1b5e20' : '#7a4a00'}}>Avail {selected.asset_availability_pct}%</span>
            <span className="metric-pill">Critical Avail <strong>{selected.critical_asset_availability_pct}%</strong></span>
            <span className="metric-pill">Completion <strong>{selected.maintenance_completion_rate}%</strong></span>
            <span className="metric-pill" style={{background: (selected.duration_variance_minutes ?? 0) >0 ? '#ffebee' : '#e8f5e9', borderColor: (selected.duration_variance_minutes ?? 0) >0 ? '#ffcdd2' : '#c8e6c9', color: (selected.duration_variance_minutes ?? 0) >0 ? '#7a1a1a' : '#1b5e20'}}>Δ {selected.duration_variance_minutes}m <span style={{fontWeight:500, color:'var(--text-muted)'}}>Planned {selected.planned_duration_minutes}m → Actual {selected.actual_duration_minutes}m</span></span>
          </div>
          <details style={{fontSize:11, marginTop:10, background:'#f8fafb', border:'1px solid #eef2f6', borderRadius:4, padding:'6px 8px'}}>
            <summary style={{fontWeight:700, cursor:'pointer', color:'var(--text-secondary)'}}>Formulas</summary>
            <pre className="mono" style={{background:'white', padding:8, fontSize:11, whiteSpace:'pre-wrap', wordBreak:'break-word', border:'1px solid #e0e6ed', borderRadius:4, marginTop:8, maxHeight:140, overflow:'auto'}}>{JSON.stringify((selected as unknown as {formulas:unknown}).formulas, null, 2)}</pre>
          </details>
        </Card>

        <Card title="Completion">
          <div style={{height:200}}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={completionData} cx="50%" cy="50%" outerRadius={70} dataKey="value" label={({name, value})=>`${name} ${value}%`}>
                  {completionData.map((_, i)=><Cell key={i} fill={PIE_COLORS[i%PIE_COLORS.length]} stroke="white" strokeWidth={1} />)}
                </Pie>
                <Tooltip contentStyle={{borderRadius:8, border:'1px solid #e0e6ed', fontSize:12}} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <Card title="Baseline vs Optimized (From DB)">
        <MetricsChart baseline={(selected.baseline || selected.baseline_metrics) as Record<string,unknown>} optimized={(selected.optimized || selected.optimized_metrics) as Record<string,unknown>} />
        <div style={{display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(260px, 1fr))', gap:12, marginTop:10}}>
          <div style={{background:'#f8fafb', padding:10, borderRadius:8, border:'1px solid #eef2f6'}}>
            <div style={{fontSize:10.5, fontWeight:700, letterSpacing:0.4, textTransform:'uppercase', color:'var(--text-secondary)', marginBottom:6, display:'flex', alignItems:'center', gap:6}}>Baseline / Optimized / Improvement <span className="pill" style={{background:'var(--chart-navy)', color:'white', borderColor:'var(--chart-navy)', fontSize:10, padding:'1px 6px'}}>Navy</span></div>
            <pre className="mono" style={{fontSize:11, lineHeight:1.4, margin:0, whiteSpace:'pre-wrap', wordBreak:'break-word', background:'white', border:'1px solid #e0e6ed', borderRadius:4, padding:8, maxHeight:180, overflow:'auto'}}>{JSON.stringify({baseline: selected.baseline, optimized: selected.optimized, improvement: selected.improvement}, null, 2)}</pre>
          </div>
          <div style={{background:'#f0f7f7', padding:10, borderRadius:8, border:'1px solid #c2e8e8'}}>
            <div style={{fontSize:10.5, fontWeight:700, letterSpacing:0.4, textTransform:'uppercase', color:'var(--text-secondary)', marginBottom:6, display:'flex', alignItems:'center', gap:6}}>Objective · Dataset <span className="pill" style={{background:'var(--teal)', color:'white', borderColor:'var(--teal)', fontSize:10, padding:'1px 6px'}}>Teal</span></div>
            <pre className="mono" style={{fontSize:11, lineHeight:1.4, margin:0, whiteSpace:'pre-wrap', wordBreak:'break-word', background:'white', border:'1px solid #e0e6ed', borderRadius:4, padding:8, maxHeight:180, overflow:'auto'}}>{JSON.stringify(selected.objective_breakdown, null,2)}</pre>
          </div>
        </div>
      </Card>

      <Card title="Asset Breakdown (Top 6)">
        <div style={{height:250}}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={assetChartData} barGap={6}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef2f6" />
              <XAxis dataKey="name" tick={{fontSize:11, fill:'#5a6a7a'}} axisLine={{stroke:'#e0e6ed'}} tickLine={{stroke:'#e0e6ed'}} />
              <YAxis tick={{fontSize:11, fill:'#5a6a7a'}} axisLine={{stroke:'#e0e6ed'}} tickLine={{stroke:'#e0e6ed'}} width={32} />
              <Tooltip cursor={{fill:'rgba(45,139,139,0.06)'}} contentStyle={{borderRadius:8, border:'1px solid #e0e6ed', fontSize:12}} />
              <Legend wrapperStyle={{fontSize:11, paddingTop:6}} />
              <Bar dataKey="downtime" fill="#f44336" name="Downtime" radius={[4,4,0,0]} />
              <Bar dataKey="available" fill="#2d8b8b" name="Available" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="rb-table-wrap" style={{maxHeight:200, overflow:'auto', marginTop:10}}>
          <table className="rb-table">
            <thead><tr><th>Asset</th><th>Downtime</th><th>Available</th><th>%</th></tr></thead>
            <tbody>
              {Object.entries(selected.asset_metrics || {}).map(([aid, m])=><tr key={aid}><td className="mono" style={{fontSize:11, fontWeight:600}}>{aid}</td><td className="mono" style={{fontSize:11}}>{(m as {downtime_minutes:number}).downtime_minutes}</td><td className="mono" style={{fontSize:11}}>{(m as {available_minutes:number}).available_minutes}</td><td><span className="pill" style={{background: (m as {availability_pct:number}).availability_pct>80?'#e8f5e9':'#fff8e1', color:(m as {availability_pct:number}).availability_pct>80?'#1b5e20':'#7a4a00', borderColor:(m as {availability_pct:number}).availability_pct>80?'#c8e6c9':'#ffecb3', fontSize:11}}>{(m as {availability_pct:number}).availability_pct}%</span></td></tr>)}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Planned vs Actual (Per Block)">
        <div style={{height:300}}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={plannedActualData} barGap={6}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef2f6" />
              <XAxis dataKey="name" tick={{fontSize:11, fill:'#5a6a7a'}} axisLine={{stroke:'#e0e6ed'}} tickLine={{stroke:'#e0e6ed'}} />
              <YAxis tick={{fontSize:11, fill:'#5a6a7a'}} axisLine={{stroke:'#e0e6ed'}} tickLine={{stroke:'#e0e6ed'}} width={36} />
              <Tooltip cursor={{fill:'rgba(45,139,139,0.06)'}} contentStyle={{borderRadius:8, border:'1px solid #e0e6ed', fontSize:12}} />
              <Legend wrapperStyle={{fontSize:11, paddingTop:6}} />
              <Bar dataKey="planned" fill="#0f2a44" name="Planned" radius={[4,4,0,0]} />
              <Bar dataKey="actual" fill="#2d8b8b" name="Actual" radius={[4,4,0,0]} />
              <Bar dataKey="variance" fill="#ff9800" name="Variance" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <pre className="mono" style={{fontSize:11, maxHeight:180, overflow:'auto', background:'#f8fafb', padding:10, border:'1px solid #eef2f6', borderRadius:4, marginTop:10, whiteSpace:'pre-wrap', wordBreak:'break-word'}}>{JSON.stringify(selected.planned_vs_actual, null,2)}</pre>
      </Card>

      <Card title="Validation">
        <pre className="mono" style={{fontSize:11, lineHeight:1.4, whiteSpace:'pre-wrap', wordBreak:'break-word', background: selected.validation?.valid ? '#e8f5e9' : '#ffebee', padding:10, borderRadius:4, border:`1px solid ${selected.validation?.valid ? '#c8e6c9' : '#ffcdd2'}`, margin:0, maxHeight:200, overflow:'auto'}}>{JSON.stringify(selected.validation, null,2)}</pre>
      </Card>
    </div>}
  </div>
}
