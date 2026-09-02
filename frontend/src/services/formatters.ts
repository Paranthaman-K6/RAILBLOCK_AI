export const minutesToTime = (m: number | string | null | undefined) => {
  if (m === null || m === undefined || m === '') return '-'
  const num = typeof m === 'string' ? Number(m) : m
  if (Number.isNaN(num)) return '-'
  const h = Math.floor(num/60).toString().padStart(2,'0')
  const mm = (num%60).toString().padStart(2,'0')
  return `${h}:${mm}`
}
export const timeToMinutes = (t: string) => {
  if (!t || typeof t !== 'string' || t.trim() === '') return 0
  const [h,m]=t.split(':').map(Number)
  return (Number.isNaN(h) ? 0 : h)*60 + (Number.isNaN(m) ? 0 : m)
}
export const formatDateKolkata = (dateStr: string) => {
  if (!dateStr) return '-'
  try {
    // Input YYYY-MM-DD, display as DD/MM/YYYY in Asia/Kolkata
    const d = new Date(dateStr + 'T00:00:00')
    return d.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', day:'2-digit', month:'2-digit', year:'numeric' })
  } catch { return dateStr }
}
export const formatDateTimeKolkata = (iso: string) => {
  if (!iso) return '-'
  try {
    const d = new Date(iso)
    return d.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', dateStyle:'medium', timeStyle:'short' })
  } catch { return iso }
}
