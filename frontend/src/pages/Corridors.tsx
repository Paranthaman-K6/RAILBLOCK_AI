import { useEffect, useState, useMemo } from 'react'
import api from '../services/api'
import Card from '../components/Card'
import type { Corridor, Asset } from '../types'

export default function Corridors() {
  const [cors, setCors] = useState<Corridor[]>([])
  const [assets, setAssets] = useState<Asset[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    Promise.all([api.get('/api/corridors'), api.get('/api/assets')])
      .then(([cRes, aRes]) => {
        if (cancelled) return
        const cData = cRes.data as Corridor[] | { corridors?: Corridor[] }
        const aData = aRes.data as Asset[] | { assets?: Asset[] }
        setCors(Array.isArray(cData) ? cData : (cData as { corridors?: Corridor[] }).corridors || [])
        setAssets(Array.isArray(aData) ? aData : (aData as { assets?: Asset[] }).assets || [])
      })
      .catch(() => {
        // keep empty, error handled by empty-state
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const term = search.trim().toLowerCase()

  const filteredCorridors = useMemo(() => {
    if (!term) return cors
    return cors.filter((c) => c.corridor_id.toLowerCase().includes(term) || c.name.toLowerCase().includes(term))
  }, [cors, term])

  const filteredAssets = useMemo(() => {
    if (!term) return assets
    return assets.filter(
      (a) =>
        a.asset_id.toLowerCase().includes(term) ||
        a.corridor_id.toLowerCase().includes(term) ||
        (a.section_id && a.section_id.toLowerCase().includes(term)) ||
        (a.line_id && a.line_id.toLowerCase().includes(term)) ||
        a.asset_type.toLowerCase().includes(term),
    )
  }, [assets, term])

  return (
    <div className="page-wrap">
      <div className="page-header">
        <h1>Corridors &amp; Assets</h1>
        <div className="page-subtitle">Network topology COR / SEC / LIN / AST · from COA</div>
      </div>

      <div className="filter-bar">
        <div style={{ flex: '1 1 260px', minWidth: 200 }}>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search corridor or asset id…"
            className="rb-input"
            style={{ width: '100%' }}
            aria-label="Search corridor or asset"
          />
        </div>
        <span className="pill pill--count">Corridors {cors.length}</span>
        <span className="pill pill--count">Assets {assets.length}</span>
        {term && (
          <span className="pill pill--muted" style={{ fontSize: 11 }}>
            filtered · {filteredCorridors.length} corr · {filteredAssets.length} assets
          </span>
        )}
      </div>

      <Card title="Corridors" action={<span className="pill pill--count">{filteredCorridors.length} shown</span>}>
        <div className="rb-card-desc" style={{ marginTop: -2 }}>
          GET /api/corridors · corridor_id is synthetic COR-* · name is display label
        </div>
        {loading ? (
          <div className="rb-table-wrap">
            <table className="rb-table">
              <thead>
                <tr>
                  <th>Corridor</th>
                  <th>Name</th>
                </tr>
              </thead>
              <tbody>
                {[0, 1, 2].map((k) => (
                  <tr key={k}>
                    <td>
                      <div className="skeleton" style={{ height: 18, width: 90 }} />
                    </td>
                    <td>
                      <div className="skeleton" style={{ height: 18, width: 160 }} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : filteredCorridors.length === 0 ? (
          <div className="empty-state">No corridors — {term ? `no match for “${search}”` : 'backend returned none. Check /api/corridors.'}</div>
        ) : (
          <div className="rb-table-wrap">
            <table className="rb-table">
              <thead>
                <tr>
                  <th>Corridor</th>
                  <th>Name</th>
                </tr>
              </thead>
              <tbody>
                {filteredCorridors.map((c) => (
                  <tr key={c.corridor_id}>
                    <td>
                      <span className="mono-pill" style={{ fontSize: 11 }}>
                        {c.corridor_id}
                      </span>
                    </td>
                    <td style={{ fontSize: 12.5 }}>{c.name}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Assets" action={<span className="pill pill--count">{filteredAssets.length} shown · {assets.length} total</span>}>
        <div className="rb-card-desc" style={{ marginTop: -2 }}>
          GET /api/assets · AST-* · filter by search above · corridor / section / line / type
        </div>
        {loading ? (
          <div className="rb-table-wrap">
            <table className="rb-table">
              <thead>
                <tr>
                  <th>Asset</th>
                  <th>Corridor</th>
                  <th>Section</th>
                  <th>Line</th>
                  <th>Type</th>
                </tr>
              </thead>
              <tbody>
                {[0, 1, 2].map((k) => (
                  <tr key={k}>
                    <td>
                      <div className="skeleton" style={{ height: 16, width: 80 }} />
                    </td>
                    <td>
                      <div className="skeleton" style={{ height: 16, width: 70 }} />
                    </td>
                    <td>
                      <div className="skeleton" style={{ height: 16, width: 60 }} />
                    </td>
                    <td>
                      <div className="skeleton" style={{ height: 16, width: 60 }} />
                    </td>
                    <td>
                      <div className="skeleton" style={{ height: 16, width: 70 }} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : filteredAssets.length === 0 ? (
          <div className="empty-state">No assets — {term ? `no match for “${search}”` : 'backend returned none.'}</div>
        ) : (
          <div className="rb-table-wrap">
            <table className="rb-table">
              <thead>
                <tr>
                  <th>Asset</th>
                  <th>Corridor</th>
                  <th>Section</th>
                  <th>Line</th>
                  <th>Type</th>
                </tr>
              </thead>
              <tbody>
                {filteredAssets.map((a) => (
                  <tr key={a.asset_id}>
                    <td>
                      <span className="mono-pill mono-pill--teal" style={{ fontSize: 11 }}>
                        {a.asset_id}
                      </span>
                    </td>
                    <td>
                      <span className="mono-pill" style={{ fontSize: 11 }}>
                        {a.corridor_id}
                      </span>
                    </td>
                    <td style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{a.section_id || '—'}</td>
                    <td style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{a.line_id || '—'}</td>
                    <td>
                      <span className="pill pill--muted" style={{ fontSize: 11 }}>
                        {a.asset_type}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!loading && assets.length > 30 && filteredAssets.length === assets.length && (
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>Showing {assets.length} assets · use search to filter</div>
        )}
      </Card>
    </div>
  )
}
