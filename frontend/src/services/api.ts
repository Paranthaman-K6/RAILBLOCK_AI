import axios from 'axios'

const _viteEnv = ((import.meta as unknown as { env?: Record<string, string> }).env) || (import.meta as unknown as { env: Record<string, string> }).env || {}
const _rawBase: string = _viteEnv.VITE_API_URL ?? ''
// Production fallback for Vercel split deployment: Render backend. Prevents silent localhost/empty misbake.
// Local dev uses vite proxy (VITE_API_URL empty → same-origin → proxy). On Vercel prod, dashboard must set VITE_API_URL.
const RENDER_FALLBACK = 'https://railblock-ai-up0g.onrender.com'
let _resolvedBase = _rawBase
if (import.meta.env.PROD && !_resolvedBase) {
  // Empty in production on Vercel means env var not set — fall back to Render instead of same-origin 404
  console.warn(`[RailBlock] VITE_API_URL empty in production — falling back to ${RENDER_FALLBACK}. Set VITE_API_URL in Vercel dashboard to suppress.`)
  _resolvedBase = RENDER_FALLBACK
}
if (_resolvedBase.includes('localhost')) {
  const msg = `[RailBlock] VITE_API_URL contains localhost in production (${_resolvedBase}) — this will fail on Vercel. Use ${RENDER_FALLBACK}`
  if (import.meta.env.PROD) console.error(msg)
  else console.warn(msg)
  // In production, auto-correct localhost to Render to avoid broken deploy
  if (import.meta.env.PROD) _resolvedBase = RENDER_FALLBACK
}
// Strip trailing slashes so `${baseURL}/health` never becomes `//health`
const _apiBase = _resolvedBase.replace(/\/+$/, '')
const api = axios.create({
  baseURL: _apiBase,
  headers: { 'Content-Type': 'application/json' },
})

// Add department header from localStorage
api.interceptors.request.use((config) => {
  const dept = localStorage.getItem('department') || 'VIEWER'
  config.headers['X-Department'] = dept
  return config
})

export default api

// helpers
export const health = () => api.get('/health')
export const getTasks = (params?: Record<string, unknown>) => api.get('/api/tasks', { params })
export const getPlans = (params?: Record<string, unknown>) => api.get('/api/plans', { params })
export const generatePlan = (payload: Record<string, unknown>) => api.post('/api/plans/generate', payload)
export const getPlan = (id: string) => api.get(`/api/plans/${id}`)
export const validatePlan = (id: string) => api.post(`/api/plans/${id}/validate`)
export const approvePlan = (id: string, payload: Record<string, unknown>) => api.post(`/api/plans/${id}/approve`, payload)
export const rejectPlan = (id: string, payload: Record<string, unknown>) => api.post(`/api/plans/${id}/reject`, payload)
export const submitReview = (id: string) => api.post(`/api/plans/${id}/submit-review`)
export const getApprovedPlans = (dept?: string) => api.get('/api/approved-plans', { params: { department: dept } })
export const getDeptView = (planId: string, dept: string) => api.get(`/api/plans/${planId}/department-view`, { params: { department: dept } })
export const getNotifications = (dept: string) => api.get('/api/notifications', { params: { department: dept } })
export const recordExecution = (blockId: string, payload: Record<string, unknown>) => api.post(`/api/blocks/${blockId}/execution`, payload)
export const getMetrics = (planId?: string) => (planId ? api.get(`/api/metrics/${planId}`) : api.get('/api/metrics'))
export const getWindows = (params?: Record<string, unknown>) => api.get('/api/windows', { params })
export const detectConflicts = (payload: Record<string, unknown>) => api.post('/api/conflicts/detect', payload)
export const deletePlan = (planId: string, actor?: Record<string, unknown>) => api.delete(`/api/plans/${planId}`, { data: actor || {} })
export const bulkDeletePlans = (planIds: string[], actor?: Record<string, unknown>) => api.post('/api/plans/bulk-delete', { plan_ids: planIds, ...(actor || {}) })
export const importFile = (url: string, file: File, source: string) => {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('source', source)
  return api.post(url, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
}
