import { useState } from 'react'
import api from '../services/api'
import { formatError } from '../services/errors'

type ImportResult = {
  source_name: string
  import_run_id: string
  received_count: number
  accepted_count: number
  rejected_count: number
  duplicate_count: number
  warning_count: number
  errors: unknown[]
  warnings: unknown[]
}

function UploadIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="#4a5a6e" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M12 16V3M8 7l4-4 4 4" />
      <path d="M4 17v2a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-2H4z" />
    </svg>
  )
}

function ImportEmptyIcon() {
  return (
    <svg width={28} height={28} viewBox="0 0 24 24" fill="none" stroke="#8896a8" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6M10 13H8M16 17H8M13 13h3" />
    </svg>
  )
}

function UploadZone({
  id,
  label,
  hint,
  onChange,
  secondaryId,
  secondaryLabel,
  onSecondaryChange,
}: {
  id: string
  label: string
  hint: string
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  secondaryId?: string
  secondaryLabel?: string
  onSecondaryChange?: (e: React.ChangeEvent<HTMLInputElement>) => void
}) {
  const hasTwo = !!secondaryId
  if (hasTwo) {
    return (
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <label
          htmlFor={id}
          style={{
            flex: '1 1 160px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 6,
            border: '1.5px dashed #d0d8e4',
            borderRadius: 8,
            padding: 14,
            background: '#fbfcfe',
            cursor: 'pointer',
            transition: 'border-color 0.15s, background 0.15s',
            minHeight: 96,
            textAlign: 'center',
          }}
          onMouseEnter={(e) => ((e.currentTarget.style.borderColor = 'var(--teal)'), (e.currentTarget.style.background = '#f0f7f7'))}
          onMouseLeave={(e) => ((e.currentTarget.style.borderColor = '#d0d8e4'), (e.currentTarget.style.background = '#fbfcfe'))}
        >
          <UploadIcon />
          <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-primary)' }}>{label}</span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Drop CSV or click to browse</span>
          <span className="mono-pill" style={{ fontSize: 10, padding: '2px 6px', marginTop: 2 }}>
            .csv
          </span>
          <span style={{ fontSize: 10.5, color: 'var(--text-muted)', marginTop: 2 }}>{hint}</span>
        </label>
        <input id={id} type="file" accept=".csv" onChange={onChange} style={{ display: 'none' }} />
        <label
          htmlFor={secondaryId}
          style={{
            flex: '1 1 160px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 6,
            border: '1.5px dashed #d0d8e4',
            borderRadius: 8,
            padding: 14,
            background: '#fbfcfe',
            cursor: 'pointer',
            transition: 'border-color 0.15s, background 0.15s',
            minHeight: 96,
            textAlign: 'center',
          }}
          onMouseEnter={(e) => ((e.currentTarget.style.borderColor = 'var(--teal)'), (e.currentTarget.style.background = '#f0f7f7'))}
          onMouseLeave={(e) => ((e.currentTarget.style.borderColor = '#d0d8e4'), (e.currentTarget.style.background = '#fbfcfe'))}
        >
          <UploadIcon />
          <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-primary)' }}>{secondaryLabel}</span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Drop CSV or click to browse</span>
          <span className="mono-pill" style={{ fontSize: 10, padding: '2px 6px', marginTop: 2 }}>
            .csv
          </span>
        </label>
        <input id={secondaryId} type="file" accept=".csv" onChange={onSecondaryChange} style={{ display: 'none' }} />
      </div>
    )
  }
  return (
    <>
      <label
        htmlFor={id}
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 6,
          border: '1.5px dashed #d0d8e4',
          borderRadius: 8,
          padding: 14,
          background: '#fbfcfe',
          cursor: 'pointer',
          transition: 'border-color 0.15s, background 0.15s',
          minHeight: 96,
          textAlign: 'center',
        }}
        onMouseEnter={(e) => ((e.currentTarget.style.borderColor = 'var(--teal)'), (e.currentTarget.style.background = '#f0f7f7'))}
        onMouseLeave={(e) => ((e.currentTarget.style.borderColor = '#d0d8e4'), (e.currentTarget.style.background = '#fbfcfe'))}
      >
        <UploadIcon />
        <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-primary)' }}>{label}</span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Drop CSV or click to browse</span>
        <span className="mono-pill" style={{ fontSize: 10, padding: '2px 6px', marginTop: 2 }}>
          .csv
        </span>
        <span style={{ fontSize: 10.5, color: 'var(--text-muted)', marginTop: 2 }}>{hint}</span>
      </label>
      <input id={id} type="file" accept=".csv" onChange={onChange} style={{ display: 'none' }} />
    </>
  )
}

export default function DataImport() {
  const [results, setResults] = useState<ImportResult[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handle = async (e: React.ChangeEvent<HTMLInputElement>, source: string, url: string) => {
    const file = e.target.files?.[0]
    if (!file) return
    setError('')
    setLoading(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('source', source)
      const r = await api.post(url, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      setResults((prev) => [r.data as ImportResult, ...prev])
    } catch (err: unknown) {
      setError(formatError(err))
    } finally {
      setLoading(false)
      e.target.value = ''
    }
  }

  return (
    <div className="page-wrap">
      <div className="page-header">
        <h1>Import &amp; Validate</h1>
        <div className="page-subtitle">Synthetic auto-loads · idempotent · CSV validation with row-level errors</div>
      </div>

      {/* Two top banners — rb-card--dense, avoid global banner palette clash */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 10, marginBottom: 12 }}>
        <div className="rb-card rb-card--dense" style={{ margin: 0, display: 'flex', gap: 10, alignItems: 'flex-start', background: '#f8fafb', border: '1px solid #e0e6ed' }}>
          <span style={{ width: 28, height: 28, minWidth: 28, borderRadius: 6, background: '#e3f2fd', border: '1px solid #bbdefb', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 12 }} aria-hidden>
            ◈
          </span>
          <div style={{ minWidth: 0 }}>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
              <span className="pill" style={{ background: '#e3f2fd', color: '#0d47a1', borderColor: '#bbdefb', fontSize: 10.5 }}>
                Synthetic auto-loads
              </span>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)' }}>No manual import required</span>
            </div>
            <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', lineHeight: 1.4, marginTop: 4 }}>
              Synthetic data auto-loads on first backend start — no manual import required. Import is idempotent; duplicates return deterministic counts.
            </div>
          </div>
        </div>
        <div className="rb-card rb-card--dense" style={{ margin: 0, display: 'flex', gap: 10, alignItems: 'flex-start', background: '#fffff8', border: '1px solid #ffeaa7' }}>
          <span style={{ width: 28, height: 28, minWidth: 28, borderRadius: 6, background: '#fff3cd', border: '1px solid #ffeaa7', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 12 }} aria-hidden>
            ⇅
          </span>
          <div style={{ minWidth: 0 }}>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
              <span className="pill" style={{ background: '#fff3cd', color: '#664d03', borderColor: '#ffeaa7', fontSize: 10.5 }}>
                Drag-and-drop
              </span>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)' }}>CSV validation</span>
            </div>
            <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', lineHeight: 1.4, marginTop: 4 }}>
              Drag-and-drop CSV. Shows accepted/rejected, row-level errors with row, field, severity, code, message. Idempotent duplicate detection.
            </div>
          </div>
        </div>
      </div>

      {loading && (
        <div className="loading-inline" style={{ marginBottom: 10 }}>
          <span className="spinner" aria-hidden />
          <span>Uploading… validating rows</span>
        </div>
      )}

      {error && (
        <div role="alert" style={{ color: '#7a1a1a', background: '#ffebee', padding: '10px 12px', border: '1px solid #f8bbd0', borderRadius: 4, fontSize: 12.5, lineHeight: 1.4, marginBottom: 12 }}>
          {error}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 12 }}>
        <div className="rb-card" style={{ margin: 0 }}>
          <h3 className="rb-card-title">TMS Tasks</h3>
          <div className="rb-card-desc" style={{ fontSize: 11 }}>ENGINEERING · TSK-* · severity, safety_score · POST /api/import/tasks</div>
          <UploadZone id="import-tms" label="Upload TMS CSV" hint="source=TMS" onChange={(e) => handle(e, 'TMS', '/api/import/tasks')} />
        </div>

        <div className="rb-card" style={{ margin: 0 }}>
          <h3 className="rb-card-title">SMMS</h3>
          <div className="rb-card-desc" style={{ fontSize: 11 }}>S_AND_T · signalling · POST /api/import/tasks</div>
          <UploadZone id="import-smms" label="Upload SMMS CSV" hint="source=SMMS" onChange={(e) => handle(e, 'SMMS', '/api/import/tasks')} />
        </div>

        <div className="rb-card" style={{ margin: 0 }}>
          <h3 className="rb-card-title">TDMS</h3>
          <div className="rb-card-desc" style={{ fontSize: 11 }}>TRACTION · power isolation · POST /api/import/tasks</div>
          <UploadZone id="import-tdms" label="Upload TDMS CSV" hint="source=TDMS" onChange={(e) => handle(e, 'TDMS', '/api/import/tasks')} />
        </div>

        <div className="rb-card" style={{ margin: 0 }}>
          <h3 className="rb-card-title">COA Corridors / Assets</h3>
          <div className="rb-card-desc" style={{ fontSize: 11 }}>COR-*/SEC-*/LIN-*/AST-* · two uploads · /api/import/corridors &amp; /api/import/assets</div>
          <UploadZone
            id="import-coa-corridor"
            label="Corridors CSV"
            hint="COA corridors"
            onChange={(e) => handle(e, 'COA', '/api/import/corridors')}
            secondaryId="import-coa-assets"
            secondaryLabel="Assets CSV"
            onSecondaryChange={(e) => handle(e, 'COA', '/api/import/assets')}
          />
        </div>

        <div className="rb-card" style={{ margin: 0 }}>
          <h3 className="rb-card-title">Timetable Trains</h3>
          <div className="rb-card-desc" style={{ fontSize: 11 }}>TRN-* · protected intervals · POST /api/import/trains</div>
          <UploadZone id="import-trains" label="Upload Timetable CSV" hint="source=TIMETABLE" onChange={(e) => handle(e, 'TIMETABLE', '/api/import/trains')} />
        </div>

        <div className="rb-card" style={{ margin: 0 }}>
          <h3 className="rb-card-title">Goods Forecast</h3>
          <div className="rb-card-desc" style={{ fontSize: 11 }}>confidence ≥0.7 HARD · ≥0.4 SOFT · POST /api/import/goods-forecast</div>
          <UploadZone id="import-goods" label="Upload Goods CSV" hint="source=GOODS_FORECAST" onChange={(e) => handle(e, 'GOODS_FORECAST', '/api/import/goods-forecast')} />
        </div>

        <div className="rb-card" style={{ margin: 0 }}>
          <h3 className="rb-card-title">Resources</h3>
          <div className="rb-card-desc" style={{ fontSize: 11 }}>RES-* · per-date non-overlap · POST /api/import/resources</div>
          <UploadZone id="import-resources" label="Upload Resources CSV" hint="source=RESOURCES" onChange={(e) => handle(e, 'RESOURCES', '/api/import/resources')} />
        </div>
      </div>

      <div style={{ marginTop: 14 }}>
        {results.length === 0 && !error && !loading && (
          <div className="empty-state" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, padding: 20 }}>
            <ImportEmptyIcon />
            <div style={{ fontWeight: 600, color: 'var(--text-secondary)', fontSize: 13 }}>No imports yet</div>
            <div style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>Synthetic 30 tasks auto-loaded; or choose a CSV above. Idempotent — duplicates show deterministic counts.</div>
          </div>
        )}

        {results.map((r, i) => (
          <div key={`${r.import_run_id}-${i}`} className="rb-card">
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 4 }}>
              <span className="mono-pill" style={{ fontSize: 11 }}>
                {r.import_run_id}
              </span>
              <span className="pill pill--blue" style={{ fontSize: 11 }}>
                {r.source_name}
              </span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>import result</span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8, lineHeight: 1.4 }}>Received/Accepted/Rejected with row-level errors and warnings</div>
            <div className="metric-row">
              <span className="metric-pill">
                Received <strong style={{ color: 'var(--text-primary)' }}>{r.received_count}</strong>
              </span>
              <span className="metric-pill" style={{ borderColor: '#c8e6c9', background: '#e8f5e9', color: '#1b5e20' }}>
                Accepted <strong>{r.accepted_count}</strong>
              </span>
              <span className="metric-pill" style={{ borderColor: '#f8bbd0', background: '#ffebee', color: '#7a1a1a' }}>
                Rejected <strong>{r.rejected_count}</strong>
              </span>
              <span className="metric-pill">Duplicate <strong>{r.duplicate_count}</strong></span>
              <span className="metric-pill" style={{ borderColor: '#ffe0b2', background: '#fff8e1', color: '#7a3e00' }}>
                Warnings <strong>{r.warning_count}</strong>
              </span>
            </div>
            {r.errors.length > 0 && (
              <details style={{ marginTop: 10, background: '#fff', border: '1px solid #f8bbd0', borderRadius: 4, padding: '8px 10px' }}>
                <summary style={{ fontSize: 12, fontWeight: 700, cursor: 'pointer', color: '#7a1a1a' }}>Errors ({r.errors.length})</summary>
                <pre
                  style={{
                    background: '#ffebee',
                    color: '#7a1a1a',
                    padding: 10,
                    maxHeight: 200,
                    overflow: 'auto',
                    border: '1px solid #f8bbd0',
                    borderRadius: 4,
                    marginTop: 8,
                    fontSize: 11,
                    lineHeight: 1.4,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {JSON.stringify(r.errors, null, 2)}
                </pre>
              </details>
            )}
            {r.warnings.length > 0 && (
              <details style={{ marginTop: 8, background: '#fff', border: '1px solid #ffe0b2', borderRadius: 4, padding: '8px 10px' }}>
                <summary style={{ fontSize: 12, fontWeight: 700, cursor: 'pointer', color: '#7a4a00' }}>Warnings ({r.warnings.length})</summary>
                <pre
                  style={{
                    background: '#fff8e1',
                    color: '#5a3e00',
                    padding: 10,
                    maxHeight: 160,
                    overflow: 'auto',
                    border: '1px solid #ffecb3',
                    borderRadius: 4,
                    marginTop: 8,
                    fontSize: 11,
                    lineHeight: 1.4,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {JSON.stringify(r.warnings, null, 2)}
                </pre>
              </details>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
