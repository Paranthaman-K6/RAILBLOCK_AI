import { useEffect, useState } from 'react'
import { DEPARTMENTS } from '../constants/departments'
import { IconMenu } from './icons'

type Props = {
  onBurger: () => void
}

export default function Topbar({ onBurger }: Props) {
  const [dept, setDept] = useState<string>(() => {
    try {
      return localStorage.getItem('department') || 'VIEWER'
    } catch {
      return 'VIEWER'
    }
  })

  // Keep localStorage in sync when dept changes via this component
  useEffect(() => {
    try {
      localStorage.setItem('department', dept)
    } catch {}
  }, [dept])

  // Listen for changes from Sidebar or other tabs
  useEffect(() => {
    const handleChange = () => {
      try {
        setDept(localStorage.getItem('department') || 'VIEWER')
      } catch {}
    }
    window.addEventListener('rb_department_change', handleChange)
    // also listen to storage events for cross-tab sync
    window.addEventListener('storage', handleChange as EventListener)
    return () => {
      window.removeEventListener('rb_department_change', handleChange)
      window.removeEventListener('storage', handleChange as EventListener)
    }
  }, [])

  return (
    <header className="topbar">
      <button
        className="topbar-burger"
        onClick={onBurger}
        aria-label="Toggle navigation"
        type="button"
      >
        <IconMenu size={18} />
      </button>
      <span className="topbar-title">RailBlock AI</span>
      <div className="topbar-dept">
        <select
          value={dept}
          onChange={(e) => {
            const v = e.target.value
            setDept(v)
            try {
              localStorage.setItem('department', v)
              window.dispatchEvent(new Event('rb_department_change'))
            } catch {}
          }}
          aria-label="Select department"
        >
          {DEPARTMENTS.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
      </div>
    </header>
  )
}
