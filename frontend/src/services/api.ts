import axios from 'axios'

const _viteEnv = ((import.meta as unknown as { env?: Record<string, string> }).env) || (import.meta as unknown as { env: Record<string, string> }).env || {}
const _rawBase: string = _viteEnv.VITE_API_URL ?? ''
// Strip trailing slashes so `${baseURL}/health` never becomes `//health`; empty stays same-origin (Render single-image)
// On Vercel, set VITE_API_URL=https://railblock-ai-up0g.onrender.com (see .env.vercel.example); on Render Docker it stays "" for same-origin
const _apiBase = _rawBase.replace(/\/+$/, '')
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
export const importFile = (url: string, file: File, source: string) => {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('source', source)
  return api.post(url, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
}
