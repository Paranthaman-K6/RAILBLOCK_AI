import type { ValidationResult } from '../types'

interface Props {
  validation: ValidationResult | null | undefined
}

export default function ValidationPanel({ validation }: Props) {
  if (!validation) return null
  return (
    <div style={{ background: validation.valid ? '#e8f5e9' : '#ffebee', padding: 12, borderRadius: 8, margin: '8px 0' }}>
      <strong>Validation: {validation.valid ? 'PASSED' : 'FAILED'}</strong>
      {!validation.valid && (
        <ul>
          {validation.violations.map((v, i) => (
            <li key={i}>
              <code>{v.code}</code> - {v.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
