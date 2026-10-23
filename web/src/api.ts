import type { DayDetail, DaySummary, Summary } from './types'

async function getJson<T>(path: string): Promise<T> {
  const resp = await fetch(path)
  if (!resp.ok) throw new Error(`Request failed: ${path} (${resp.status})`)
  return resp.json() as Promise<T>
}

export const fetchDays = () => getJson<DaySummary[]>('/api/days')
export const fetchDay = (date: string) => getJson<DayDetail>(`/api/days/${date}`)
export const fetchSummary = () => getJson<Summary>('/api/summary')

export const fmtMw = (v: number | null | undefined): string =>
  v === null || v === undefined ? 'n/a' : `${Math.round(v).toLocaleString('en-GB')} MW`

export const fmtSignedMw = (v: number | null | undefined): string => {
  if (v === null || v === undefined) return 'n/a'
  const sign = v > 0 ? '+' : ''
  return `${sign}${Math.round(v).toLocaleString('en-GB')} MW`
}

export const timeLabel = (iso: string): string => {
  const d = new Date(iso)
  return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })
}

export const publishLabel = (iso: string): string => {
  const d = new Date(iso)
  const day = d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' })
  return `${day} ${timeLabel(iso)}`
}
