import type { ReactNode, CSSProperties } from 'react'

interface CardProps {
  title: string
  children: ReactNode
  className?: string
  action?: ReactNode
  style?: CSSProperties
  accent?: boolean
}

export default function Card({ title, children, className, action, style, accent }: CardProps) {
  const accentClass = accent ? 'rb-card--accent' : ''
  const cls = `rb-card ${accentClass} ${className ?? ''}`.trim().replace(/\s+/g, ' ')
  return (
    <div className={cls} style={style}>
      {(title || action) && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: title ? 2 : 0 }}>
          {title ? <h3 className="rb-card-title">{title}</h3> : <span />}
          {action}
        </div>
      )}
      <div>{children}</div>
    </div>
  )
}
