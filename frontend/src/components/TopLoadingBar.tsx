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
      setProgress(10)
      if(timerRef.current) window.clearInterval(timerRef.current)
      // trickle progress
      timerRef.current = window.setInterval(()=>{
        setProgress(p=> Math.min(p + Math.random()*15, 85))
      }, 250) as unknown as number
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
      setTimeout(()=>{ setActive(false); setProgress(0) }, 220)
    }
    startFn = start
    doneFn = done
    // also end on route change (other option)
    const onRoute = ()=> done()
    window.addEventListener('popstate', onRoute)
    return ()=>{
      if(timerRef.current) window.clearInterval(timerRef.current)
      if(timeoutRef.current) window.clearTimeout(timeoutRef.current)
      window.removeEventListener('popstate', onRoute)
      startFn=null; doneFn=null
    }
  },[])

  if(!active && progress===0) return null
  return (
    <div aria-hidden style={{
      position:'fixed', top:0, left:0, right:0, height:3, zIndex:9999,
      background:'transparent', pointerEvents:'none'
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
