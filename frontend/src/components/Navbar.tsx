import { Link } from 'react-router-dom'
import { useState, useEffect } from 'react'

export default function Navbar(){
  const [dept, setDept] = useState(localStorage.getItem('department')||'VIEWER')
  useEffect(()=>{ localStorage.setItem('department', dept)},[dept])
  // Keep department consistent across reloads - single source of truth
  useEffect(()=>{
    const onStorage = ()=> setDept(localStorage.getItem('department')||'VIEWER')
    window.addEventListener('storage', onStorage)
    return ()=> window.removeEventListener('storage', onStorage)
  },[])
  return (
    <nav style={{display:'flex', gap:12, padding:12, background:'#0f2a44', color:'white', alignItems:'center', flexWrap:'wrap'}}>
      <strong>RailBlock AI</strong><small style={{opacity:0.8}}>Human-approved prototype</small>
      <Link to="/" style={{color:'white'}}>Dashboard</Link>
      <Link to="/import" style={{color:'white'}}>Import</Link>
      <Link to="/tasks" style={{color:'white'}}>Tasks</Link>
      <Link to="/planner" style={{color:'white'}}>Planner</Link>
      <Link to="/departments" style={{color:'white'}}>Departments</Link>
      <Link to="/execution" style={{color:'white'}}>Execution</Link>
      <Link to="/metrics" style={{color:'white'}}>Metrics</Link>
      <Link to="/conflicts" style={{color:'white'}}>Conflicts</Link>
      <select value={dept} onChange={e=>setDept(e.target.value)} style={{marginLeft:'auto'}}>
        <option>CONTROL_OFFICE</option><option>ENGINEERING</option><option>S_AND_T</option><option>TRACTION</option><option>PROJECTS</option><option>VIEWER</option><option>ADMIN</option>
      </select>
    </nav>
  )
}
