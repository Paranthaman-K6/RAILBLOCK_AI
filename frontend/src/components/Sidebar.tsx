import { NavLink } from 'react-router-dom'
import { useEffect, useState, useMemo } from 'react'
import { DEPARTMENTS, DEPARTMENT_LABELS } from '../constants/departments'
import {
  IconDashboard, IconImport, IconTasks, IconPlanner, IconDepartments, IconExecution,
  IconMetrics, IconCorridors, IconTrains, IconConflicts, IconOptimizer,
  IconChevronLeft, IconChevronRight,
} from './icons'

type Props = {
  collapsed: boolean
  onToggle: () => void
  mobileOpen: boolean
  onMobileClose: () => void
}

const NAV_GROUPS: { label: string; items: { to: string; label: string; icon: React.ReactNode; badge?: string }[] }[] = [
  {
    label: 'Overview',
    items: [
      { to: '/', label: 'Dashboard', icon: <IconDashboard /> },
    ],
  },
  {
    label: 'Data',
    items: [
      { to: '/import', label: 'Import', icon: <IconImport /> },
      { to: '/corridors', label: 'Corridors', icon: <IconCorridors /> },
      { to: '/trains', label: 'Trains & Windows', icon: <IconTrains /> },
      { to: '/conflicts', label: 'Conflicts', icon: <IconConflicts /> },
    ],
  },
  {
    label: 'Planning',
    items: [
      { to: '/tasks', label: 'Tasks', icon: <IconTasks /> },
      { to: '/planner', label: 'Planner', icon: <IconPlanner />, badge: '★' },
      { to: '/optimizer', label: 'Optimizer', icon: <IconOptimizer /> },
    ],
  },
  {
    label: 'Operations',
    items: [
      { to: '/departments', label: 'Departments', icon: <IconDepartments /> },
      { to: '/execution', label: 'Execution', icon: <IconExecution /> },
    ],
  },
  {
    label: 'Analytics',
    items: [
      { to: '/metrics', label: 'Metrics', icon: <IconMetrics /> },
    ],
  },
]

export default function Sidebar({ collapsed, onToggle, mobileOpen, onMobileClose }: Props) {
  const [dept, setDept] = useState<string>(() => {
    try { return localStorage.getItem('department') || 'VIEWER' } catch { return 'VIEWER' }
  })
  const [healthOk, setHealthOk] = useState<boolean | null>(null)
  const [counts, setCounts] = useState<{ tasks?: number; windows?: number; plans?: number }>({})

  // Sync department across tabs and on storage events
  useEffect(() => {
    try { localStorage.setItem('department', dept) } catch {}
    const onStorage = (e: StorageEvent) => {
      if (e.key === 'department' && e.newValue) setDept(e.newValue)
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [dept])

  // Also listen for custom event when other component updates dept
  useEffect(() => {
    const h = () => {
      try { setDept(localStorage.getItem('department') || 'VIEWER') } catch {}
    }
    window.addEventListener('rb_department_change', h)
    return () => window.removeEventListener('rb_department_change', h)
  }, [])

  // Health dot + micro live counts (poll lightweight every 30s)
  useEffect(() => {
    let cancelled = false
    const fetchMeta = async () => {
      try {
        const mod = await import('../services/api')
        const api = mod.default
        const results = await Promise.allSettled([
          api.get('/health'),
          api.get('/api/tasks?limit=1'),
          api.get('/api/windows?status=FEASIBLE'),
          api.get('/api/plans'),
        ])
        if (cancelled) return
        if (results[0].status === 'fulfilled') {
          const h: any = (results[0] as any).value.data
          setHealthOk(h?.diagnostics?.journal_mode === 'wal')
        } else setHealthOk(false)
        const c: typeof counts = {}
        if (results[1].status === 'fulfilled') {
          const d: any = (results[1] as any).value.data
          c.tasks = Array.isArray(d) ? d.length : d.total ?? d.tasks?.length ?? 0
        }
        if (results[2].status === 'fulfilled') {
          const d: any = (results[2] as any).value.data
          c.windows = Array.isArray(d) ? d.length : 0
        }
        if (results[3].status === 'fulfilled') {
          const d: any = (results[3] as any).value.data
          c.plans = Array.isArray(d) ? d.length : 0
        }
        if (!cancelled) setCounts(c)
      } catch {
        if (!cancelled) setHealthOk(false)
      }
    }
    fetchMeta()
    const id = setInterval(fetchMeta, 30000)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  const deptLabel = useMemo(() => DEPARTMENT_LABELS[dept] || dept, [dept])

  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen && <div className="sidebar-overlay" onClick={onMobileClose} aria-hidden />}

      <aside
        className={`sidebar ${collapsed ? 'collapsed' : ''} ${mobileOpen ? 'mobile-open' : ''}`}
        role="navigation"
        aria-label="Primary navigation"
      >
        <div className="sidebar-rail" aria-hidden />

        {/* Header */}
        <div className="sidebar-header">
          <div className="sidebar-logo" aria-hidden>R</div>
          {!collapsed && (
            <div className="sidebar-brand">
              <div className="sidebar-brand-title">RailBlock AI</div>
              <div className="sidebar-brand-sub">Human-approved · Prototype</div>
            </div>
          )}
          <button
            className="sidebar-toggle"
            onClick={onToggle}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            type="button"
          >
            {collapsed ? <IconChevronRight size={18} /> : <IconChevronLeft size={14} />}
          </button>
        </div>

        {/* Nav */}
        <nav className="sidebar-nav" aria-label="Sections">
          {NAV_GROUPS.map(g => (
            <div key={g.label} className="sidebar-group">
              <div className="sidebar-group-label">{g.label}</div>
              {g.items.map(it => (
                <NavLink
                  key={it.to}
                  to={it.to}
                  onClick={mobileOpen ? onMobileClose : undefined}
                  className={({ isActive }) => `sidebar-link${isActive ? ' active' : ''}`}
                  aria-current={undefined}
                  title={collapsed ? it.label : undefined}
                >
                  <span className="sidebar-icon" aria-hidden>{it.icon}</span>
                  <span className="sidebar-link-label">{it.label}</span>
                  {it.badge && <span className="sidebar-badge">{it.badge}</span>}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        {/* Collapsed expand affordance */}
        {collapsed && (
          <div className="sidebar-expand-bar" aria-hidden={false}>
            <button
              className="sidebar-expand-btn"
              onClick={onToggle}
              aria-label="Expand sidebar"
              title="Expand sidebar"
              type="button"
            >
              <IconChevronRight size={16} />
            </button>
          </div>
        )}

        {/* Footer: dept + live */}
        <div className="sidebar-footer">
          <div className="sidebar-dept-label">Department</div>
          <select
            className="sidebar-select"
            value={dept}
            onChange={e => {
              const v = e.target.value
              setDept(v)
              try {
                localStorage.setItem('department', v)
                window.dispatchEvent(new Event('rb_department_change'))
                // also dispatch storage-like for api interceptor awareness
                window.dispatchEvent(new StorageEvent('storage', { key: 'department', newValue: v } as any))
              } catch {}
            }}
            aria-label="Select department"
          >
            {DEPARTMENTS.map(d => (
              <option key={d} value={d}>{collapsed ? d.slice(0, 4) : `${d} — ${DEPARTMENT_LABELS[d] || ''}`}</option>
            ))}
          </select>
          {!collapsed && <div style={{ fontSize: 11, color: '#8aa0b8', marginTop: 6, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{deptLabel} · X-Department header</div>}

          <div className="sidebar-live" aria-live="polite">
            <span className="sidebar-live-dot" aria-hidden />
            <span>{counts.tasks ?? '—'}T · {counts.windows ?? '—'}W · {counts.plans ?? '—'}P</span>
            {!collapsed && <span style={{ marginLeft: 'auto', fontSize: 10, opacity: 0.7 }}>30s refresh</span>}
          </div>

          <div className="sidebar-health" title={healthOk === null ? 'Checking health...' : healthOk ? 'Health OK · WAL' : 'Health degraded'}>
            <span className="sidebar-health-dot" style={{ background: healthOk === null ? '#8896a8' : healthOk ? '#4caf50' : '#ff9800', boxShadow: healthOk ? '0 0 0 4px rgba(76,175,80,0.18)' : 'none' }} aria-hidden />
            <span>{healthOk === null ? 'Checking…' : healthOk ? 'WAL · Healthy' : 'Degraded'}</span>
          </div>
        </div>
      </aside>
    </>
  )
}
