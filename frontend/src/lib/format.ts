const tzOffset = () => {
  const minutes = -new Date().getTimezoneOffset()
  const sign = minutes >= 0 ? '+' : '-'
  const h = Math.floor(Math.abs(minutes) / 60)
  const m = Math.abs(minutes) % 60
  return `UTC${sign}${String(h).padStart(2, '0')}${m ? `:${String(m).padStart(2, '0')}` : ''}`
}

export const timezoneLabel = tzOffset()
export const timezoneName = Intl.DateTimeFormat().resolvedOptions().timeZone

const pad = (n: number, w = 2) => String(n).padStart(w, '0')

/** 14:03:22.481 — the console's primary time format (local time). */
export function clockTime(iso: string): string {
  const d = new Date(iso)
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${pad(d.getMilliseconds(), 3)}`
}

/** Oct 30 */
export function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

/** 2026-10-30 14:03:22.481 */
export function fullTimestamp(iso: string): string {
  const d = new Date(iso)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${clockTime(iso)}`
}

export function relativeTime(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return 'never'
  const seconds = Math.round((now - new Date(iso).getTime()) / 1000)
  if (seconds < 0) return 'just now'
  if (seconds < 45) return `${seconds}s ago`
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 48) return `${hours}h ago`
  return `${Math.round(hours / 24)}d ago`
}

export function compact(n: number): string {
  return new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 }).format(n)
}

export function integer(n: number): string {
  return new Intl.NumberFormat().format(n)
}

export function percent(ratio: number, digits = 1): string {
  return `${(ratio * 100).toFixed(digits)}%`
}

export function duration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`
  const m = Math.floor(seconds / 60)
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  if (h < 48) return `${h}h ${m % 60}m`
  return `${Math.floor(h / 24)}d ${h % 24}h`
}

/** Value for <input type="datetime-local"> from an ISO string (local time). */
export function toLocalInput(iso: string | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function fromLocalInput(value: string): string | undefined {
  if (!value) return undefined
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? undefined : d.toISOString()
}
