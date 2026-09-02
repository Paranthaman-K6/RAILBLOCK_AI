// Simple inline SVG icons — no extra dependency, control-room neutral
export function IconDashboard(props: { size?: number }) {
  const s = props.size || 18
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" />
    </svg>
  )
}
export function IconImport(props: { size?: number }) {
  const s = props.size || 18
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M12 16V3M8 7l4-4 4 4" /><path d="M3 17a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-2H3v2z" />
    </svg>
  )
}
export function IconTasks(props: { size?: number }) {
  const s = props.size || 18
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M9 5h10M9 12h10M9 19h10" /><circle cx="4.5" cy="5" r="1.5" fill="currentColor" stroke="none" /><circle cx="4.5" cy="12" r="1.5" fill="currentColor" stroke="none" /><circle cx="4.5" cy="19" r="1.5" fill="currentColor" stroke="none" />
    </svg>
  )
}
export function IconPlanner(props: { size?: number }) {
  const s = props.size || 18
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="3" y="4" width="18" height="17" rx="2" /><path d="M8 2v4M16 2v4M3 9h18" /><path d="M8 14h3M8 18h8" />
    </svg>
  )
}
export function IconDepartments(props: { size?: number }) {
  const s = props.size || 18
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  )
}
export function IconExecution(props: { size?: number }) {
  const s = props.size || 18
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M12 22c5.5 0 10-4.5 10-10S17.5 2 12 2 2 6.5 2 12s4.5 10 10 10z" /><path d="M9 12l2 2 4-4" />
    </svg>
  )
}
export function IconMetrics(props: { size?: number }) {
  const s = props.size || 18
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M3 3v18h18" /><path d="M7 16l3-3 3 3 5-8" />
    </svg>
  )
}
export function IconCorridors(props: { size?: number }) {
  const s = props.size || 18
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M3 7l9-4 9 4-9 4-9-4z" /><path d="M3 12l9 4 9-4" /><path d="M3 17l9 4 9-4" />
    </svg>
  )
}
export function IconTrains(props: { size?: number }) {
  const s = props.size || 18
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="5" y="3" width="14" height="13" rx="2" /><path d="M8 16v3M16 16v3M3 13h18" /><circle cx="9" cy="19.5" r="1" fill="currentColor" stroke="none" /><circle cx="15" cy="19.5" r="1" fill="currentColor" stroke="none" />
    </svg>
  )
}
export function IconConflicts(props: { size?: number }) {
  const s = props.size || 18
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M12 9v4M12 17h.01" /><path d="M10.3 3.3L3.3 10.3a2 2 0 0 0 0 2.8l6.7 6.7a2 2 0 0 0 2.8 0l6.7-6.7a2 2 0 0 0 0-2.8L12.6 3.3a2 2 0 0 0-2.3 0z" />
    </svg>
  )
}
export function IconOptimizer(props: { size?: number }) {
  const s = props.size || 18
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M12 3v4M12 17v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M3 12h4M17 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8" /><circle cx="12" cy="12" r="3.5" />
    </svg>
  )
}
export function IconChevronLeft(props: { size?: number }) {
  const s = props.size || 18
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M15 18l-6-6 6-6" />
    </svg>
  )
}
export function IconChevronRight(props: { size?: number }) {
  const s = props.size || 18
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M9 18l6-6-6-6" />
    </svg>
  )
}
export function IconMenu(props: { size?: number }) {
  const s = props.size || 18
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
      <path d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  )
}
export function IconX(props: { size?: number }) {
  const s = props.size || 18
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
      <path d="M18 6L6 18M6 6l12 12" />
    </svg>
  )
}
