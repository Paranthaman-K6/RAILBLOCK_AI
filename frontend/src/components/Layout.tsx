import { useState, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import Topbar from './Topbar'
import ErrorBoundary from './ErrorBoundary'

type Props = {
  children: React.ReactNode
}

export default function Layout({ children }: Props) {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem('sidebarCollapsed') === '1'
    } catch {
      return false
    }
  })
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()

  // Close mobile drawer on route change
  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])

  // Close on resize >1024 and media query listener for auto behavior
  useEffect(() => {
    const onResize = () => {
      if (window.innerWidth > 1024) setMobileOpen(false)
    }
    window.addEventListener('resize', onResize)

    const mq = window.matchMedia('(max-width: 1024px)')
    const handleMq = (e: MediaQueryListEvent) => {
      if (!e.matches) setMobileOpen(false)
    }

    // Support both modern and legacy MediaQueryList APIs
    if (mq.addEventListener) {
      mq.addEventListener('change', handleMq)
    } else {
      ;(mq as unknown as { addListener: (cb: (e: MediaQueryListEvent) => void) => void }).addListener(handleMq)
    }

    return () => {
      window.removeEventListener('resize', onResize)
      if (mq.removeEventListener) {
        mq.removeEventListener('change', handleMq)
      } else {
        ;(mq as unknown as { removeListener: (cb: (e: MediaQueryListEvent) => void) => void }).removeListener(handleMq)
      }
    }
  }, [])

  const handleToggle = () => {
    setCollapsed((c) => {
      const next = !c
      try {
        // spec: localStorage.setItem('sidebarCollapsed', collapsed?'0':'1') where collapsed is previous value
        localStorage.setItem('sidebarCollapsed', next ? '1' : '0')
      } catch {}
      return next
    })
  }

  return (
    <div className="app-shell">
      <Sidebar
        collapsed={collapsed}
        onToggle={handleToggle}
        mobileOpen={mobileOpen}
        onMobileClose={() => setMobileOpen(false)}
      />
      <div className="app-main">
        <Topbar onBurger={() => setMobileOpen((o) => !o)} />
        <div className="prototype-banner">
          <strong>Synthetic prototype data — not for real railway operations.</strong> — Prototype uses synthetic demo data only.
        </div>
        <div className="app-content">
          <ErrorBoundary>{children}</ErrorBoundary>
        </div>
        <footer className="app-footer">
          <div>
            <strong>Prototype disclaimer:</strong> This application uses synthetic demonstration data and prototype operational rules. It does not access live TMS, SMMS, TDMS, COA, timetable, or railway-control systems. It must not be used for real railway operations. Production use would require authorized data integration, railway-domain validation, cybersecurity review, safety approval, and operational certification.
          </div>
          <div style={{ marginTop: 6 }}>
            RailBlock AI — Human-approved planning and decision-support prototype. Synthetic prototype windows, not official railway availability. SQLite WAL only. No live railway APIs.
          </div>
        </footer>
      </div>
    </div>
  )
}
