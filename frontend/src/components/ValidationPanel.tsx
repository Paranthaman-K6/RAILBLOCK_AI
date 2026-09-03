import type { ValidationResult } from '../types'

interface Props {
  validation: ValidationResult | null | undefined
}

export default function ValidationPanel({ validation }: Props) {
  if (!validation) return null
  const violations = Array.isArray(validation.violations) ? validation.violations : []
  const isValid = !!validation.valid
  return (
    <div style={{ background: isValid ? '#e8f5e9' : '#ffebee', padding: 12, borderRadius: 8, margin: '8px 0' }}>
      <strong>Validation: {isValid ? 'PASSED' : 'FAILED'}</strong>
      {!isValid && (
        <ul>
          {violations.map((v, i) => (
            <li key={i}>
              <code>{v.code}</code> - {v.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
