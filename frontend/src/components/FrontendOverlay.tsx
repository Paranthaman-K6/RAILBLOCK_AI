import { useEffect, useState } from 'react'

type OverlayState = { active: boolean; message: string; sub?: string }

let setOverlay: ((s: OverlayState)=>void) | null = null
let count = 0

export const overlay = {
  show: (message="Working…", sub="Backend is processing — please wait")=>{
    count++
    setOverlay?.({active:true, message, sub})
  },
  hide: ()=>{
    count = Math.max(0, count-1)
    if(count===0) setOverlay?.({active:false, message:"", sub:""})
  },
  // force hide all (other end option)
  clear: ()=>{
    count=0
    setOverlay?.({active:false, message:"", sub:""})
  }
}

export default function FrontendOverlay(){
  const [state, setState] = useState<OverlayState>({active:false, message:"", sub:""})
  useEffect(()=>{
    setOverlay = setState
    const onKey = (e: KeyboardEvent)=>{ if(e.key==='Escape' && state.active) overlay.clear() }
    window.addEventListener('keydown', onKey)
    // also end on route change / visibility (other options)
    const onRoute = ()=> overlay.clear()
    window.addEventListener('popstate', onRoute)
    window.addEventListener('hashchange', onRoute)
    return ()=>{
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('popstate', onRoute)
      window.removeEventListener('hashchange', onRoute)
      setOverlay=null
    }
  }, [state.active])

  if(!state.active) return null
  return (
    <div role="dialog" aria-modal aria-label="Loading overlay" onClick={()=>overlay.clear()} style={{
      position:'fixed', inset:0, zIndex:9998,
      background:'rgba(15,42,68,0.42)', backdropFilter:'blur(2px)',
      display:'flex', alignItems:'center', justifyContent:'center',
      cursor:'pointer'
    }}>
      <div onClick={e=>e.stopPropagation()} style={{
        background:'white', borderRadius:12, padding:'22px 22px 18px',
        boxShadow:'0 12px 40px rgba(15,42,68,0.22)', border:'1px solid #e0e6ed',
        minWidth:320, maxWidth:420, width:'92%', textAlign:'center'
      }}>
        <div style={{display:'flex', justifyContent:'center', marginBottom:12}}>
          <span className="spinner" style={{width:28, height:28, borderWidth:3}} aria-hidden />
        </div>
        <div style={{fontWeight:800, fontSize:14, color:'var(--text-primary)', letterSpacing:-0.2}}>{state.message}</div>
        {state.sub && <div style={{fontSize:12, color:'var(--text-muted)', marginTop:6, lineHeight:1.4}}>{state.sub}</div>}
        <div style={{marginTop:14, display:'flex', gap:8, justifyContent:'center'}}>
          <button onClick={()=>overlay.clear()} className="btn btn-ghost btn-sm">Dismiss (Esc)</button>
        </div>
        <div style={{fontSize:10.5, color:'#8aa0b8', marginTop:8}}>Click overlay or press Esc to dismiss — other end option</div>
      </div>
    </div>
  )
}
