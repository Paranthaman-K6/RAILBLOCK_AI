export const HORIZONS = {
  WEEKLY: { start: '2026-09-01', end: '2026-09-07', label: 'Weekly' },
  DAILY: { start: '2026-09-01', end: '2026-09-01', label: 'Daily' },
  MONTHLY: { start: '2026-09-01', end: '2026-09-30', label: 'Monthly' },
} as const

export type HorizonType = keyof typeof HORIZONS

export const DEFAULT_HORIZON: HorizonType = 'WEEKLY'
