/**
 * Normalizes backend error envelopes to a display string.
 * Keeps {error:{code,message}} + legacy {detail} + Network Error handling,
 * and surfaces 409 duplicate-execution code explicitly.
 */
export function formatError(e: any): string {
  // New envelope {error:{code,message,details}} + legacy {detail}
  const data = e.response?.data
  const status: number | undefined = e.response?.status
  // 409 duplicate execution — always include code in message per contract
  if (status === 409) {
    if (data?.error?.message) {
      const code = data.error.code || '409_CONFLICT'
      return `[${code}] ${data.error.message}`
    }
    if (data?.detail) {
      const detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
      return `[409_CONFLICT] ${detail}`
    }
  }
  if (data?.error?.message) {
    return `${data.error.code ? '['+data.error.code+'] ' : ''}${data.error.message}`
  }
  if (data?.detail) {
    if (typeof data.detail === 'string') return data.detail
    return JSON.stringify(data.detail)
  }
  if (data?.message) return data.message
  if (e.message && e.message.includes('Network Error')) return 'API unavailable - backend may be stopped. Check http://localhost:8000/health'
  return e.message || 'Unknown error'
}
