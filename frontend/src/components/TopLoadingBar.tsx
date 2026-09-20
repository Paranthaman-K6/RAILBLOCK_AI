import { useEffect, useState, useRef } from 'react'

// Top loading bar - shows on API calls, ends on response/error
// Other options to end: timeout (8s), manual event, or route change
let startFn: (()=>void) | null = null
let doneFn: (()=>void) | null = null
export const loadingBar = {
  start: ()=> startFn?.(),
  done: ()=> doneFn?.(),
  // alternative end triggers
  timeoutMs: 8000,
}

export default function TopLoadingBar(){
  const [active, setActive] = useState(false)
  const [progress, setProgress] = useState(0)
  const timerRef = useRef<number | null>(null)
  const timeoutRef = useRef<number | null>(null)
  const countRef = useRef(0)

  useEffect(()=>{
    const start = ()=>{
      countRef.current += 1
      setActive(true)
      setProgress(12)
      if(timerRef.current) window.clearInterval(timerRef.current)
      // trickle progress
      timerRef.current = window.setInterval(()=>{
        setProgress(p=> Math.min(p + Math.random()*12, 88))
      }, 220) as unknown as number
      // safety timeout - end after 8s even if request hangs (other option to end)
      if(timeoutRef.current) window.clearTimeout(timeoutRef.current)
      timeoutRef.current = window.setTimeout(()=> done(), loadingBar.timeoutMs) as unknown as number
    }
    const done = ()=>{
      countRef.current = Math.max(0, countRef.current - 1)
      if(countRef.current > 0) return // still pending requests
      if(timerRef.current){ window.clearInterval(timerRef.current); timerRef.current=null }
      if(timeoutRef.current){ window.clearTimeout(timeoutRef.current); timeoutRef.current=null }
      setProgress(100)
      setTimeout(()=>{ setActive(false); setProgress(0) }, 240)
    }
    // other end options: route change, visibility, focus, manual, hashchange
    const onRoute = ()=> {
      // route change should force end even with pending (user navigated away)
      countRef.current = 0
      done()
    }
    const onVisible = ()=>{
      if(document.visibilityState === 'visible' && countRef.current>0){
        // if coming back after 5s and still loading, give extra 2s then force end
        if(timeoutRef.current) window.clearTimeout(timeoutRef.current)
        timeoutRef.current = window.setTimeout(()=> { countRef.current=0; done() }, 2000) as unknown as number
      }
    }
    const onFocus = ()=> {
      // focus regain is another end trigger for stuck bar
      if(countRef.current>0 && progress>80){
        setTimeout(()=> { if(countRef.current>0) { countRef.current=0; done() } }, 1000)
      }
    }
    startFn = start
    doneFn = done
    // expose manual end for long ops like Generate Plan (5s CP-SAT) - caller can call loadingBar.done()
    // also end on route/hash/visibility/focus (other options)
    window.addEventListener('popstate', onRoute)
    window.addEventListener('hashchange', onRoute)
    document.addEventListener('visibilitychange', onVisible)
    window.addEventListener('focus', onFocus)
    return ()=>{
      if(timerRef.current) window.clearInterval(timerRef.current)
      if(timeoutRef.current) window.clearTimeout(timeoutRef.current)
      window.removeEventListener('popstate', onRoute)
      window.removeEventListener('hashchange', onRoute)
      document.removeEventListener('visibilitychange', onVisible)
      window.removeEventListener('focus', onFocus)
      startFn=null; doneFn=null
    }
  },[])

  if(!active && progress===0) return null
  // other end option: click bar to force end (manual dismiss)
  const handleClick = ()=>{
    countRef.current = 0
    if(timerRef.current){ window.clearInterval(timerRef.current); timerRef.current=null }
    if(timeoutRef.current){ window.clearTimeout(timeoutRef.current); timeoutRef.current=null }
    setProgress(100)
    setTimeout(()=>{ setActive(false); setProgress(0) }, 180)
  }
  return (
    <div aria-hidden={false} aria-label="Loading, click to dismiss" title="Loading — click to dismiss (other end option)" onClick={handleClick} style={{
      position:'fixed', top:0, left:0, right:0, height:3, zIndex:9999,
      background:'transparent', cursor: progress>0 && progress<100 ? 'pointer' : 'default',
      pointerEvents: active ? 'auto' : 'none'
    }}>
      <div style={{
        height:'100%', width:`${progress}%`,
        background:'linear-gradient(90deg, var(--teal) 0%, #3aa0a0 50%, var(--status-approved) 100%)',
        boxShadow:'0 1px 6px rgba(45,139,139,0.4)',
        transition: progress===100 ? 'width 0.2s ease-out' : 'width 0.25s ease',
        opacity: active || progress===100 ? 1 : 0
      }} />
    </div>
  )
}
