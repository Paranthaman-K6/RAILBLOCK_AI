export default function WarningBanner() {
  return (
    <div
      role="alert"
      aria-live="polite"
      aria-atomic="true"
      className="prototype-banner warning-banner"
      style={{
        background: '#fff3cd',
        border: '1px solid #ffeaa7',
        padding: '8px 12px',
        marginBottom: 12,
        borderRadius: 4,
        fontSize: 12,
        lineHeight: 1.4,
        color: '#664d03',
      }}
    >
      <strong>Synthetic prototype data — not for real railway operations.</strong> This application uses synthetic demonstration data and prototype operational rules. It does not access live TMS, SMMS,
      TDMS, COA, timetable, or railway-control systems.
    </div>
  )
}

export function PrototypeDisclaimer() {
  return (
    <div
      role="alert"
      aria-live="polite"
      aria-atomic="true"
      className="prototype-banner warning-banner prototype-disclaimer"
      style={{
        background: '#fff3cd',
        border: '1px solid #ffd43b',
        padding: '10px 12px',
        margin: '12px 0',
        borderRadius: 4,
        fontSize: 12,
        lineHeight: 1.4,
        color: '#664d03',
      }}
    >
      <strong>Prototype disclaimer:</strong> This application uses synthetic demonstration data and prototype operational rules. It does not access live TMS, SMMS, TDMS, COA, timetable, or
      railway-control systems. It must not be used for real railway operations. Production use would require authorized data integration, railway-domain validation, cybersecurity review, safety
      approval, and operational certification.
    </div>
  )
}
