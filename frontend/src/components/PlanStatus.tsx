interface PlanStatusProps {
  status: string
  solver?: string
}

export default function PlanStatus({ status, solver }: PlanStatusProps) {
  // Consistent colors: Red safety risk, Orange conflict, Green feasible, Blue approved
  // Hex values preserved exactly — do not change; white-on-color passes contrast
  const color: string =
    ({
      DRAFT: '#ff9800',
      UNDER_REVIEW: '#2196f3',
      APPROVED: '#1976d2',
      PUBLISHED: '#1976d2',
      FEASIBLE: '#4caf50',
      OPTIMAL: '#4caf50',
      REJECTED: '#f44336',
      CONFLICT: '#ff9800',
      VALIDATION_FAILED: '#f44336',
      FALLBACK_USED: '#ff9800',
      SUPERSEDED: '#999',
      INFEASIBLE: '#f44336',
    } as Record<string, string>)[status] ||
    (status?.includes('FEASIBLE') ? '#4caf50' : status?.includes('APPROVED') ? '#1976d2' : '#999')
  const display = status || solver || 'UNKNOWN'
  const label = `${display}${solver && solver !== status ? ` (${solver})` : ''}`
  return (
    <span title={label} aria-label={`Plan status: ${label}`} style={{ padding: '4px 8px', background: color, color: 'white', borderRadius: 4, fontSize: 11, fontWeight: 700, letterSpacing: 0.2, whiteSpace: 'nowrap' }}>
      {display} {solver && solver !== status ? `(${solver})` : ''}
    </span>
  )
}
