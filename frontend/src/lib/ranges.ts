export interface RangePreset {
  key: string
  label: string
  hours: number | null
}

export const RANGE_PRESETS: RangePreset[] = [
  { key: '15m', label: '15m', hours: 0.25 },
  { key: '1h', label: '1h', hours: 1 },
  { key: '6h', label: '6h', hours: 6 },
  { key: '24h', label: '24h', hours: 24 },
  { key: '7d', label: '7d', hours: 24 * 7 },
  { key: '30d', label: '30d', hours: 24 * 30 },
  { key: 'all', label: 'All', hours: null },
]

export function presetStart(key: string, now = Date.now()): string | undefined {
  const preset = RANGE_PRESETS.find((p) => p.key === key)
  if (!preset?.hours) return undefined
  return new Date(now - preset.hours * 3600_000).toISOString()
}

/** Hours for the volume chart (stats API takes whole hours, max 720). */
export function chartHours(key: string): number {
  const preset = RANGE_PRESETS.find((p) => p.key === key)
  if (!preset?.hours) return 720
  return Math.min(720, Math.max(1, Math.ceil(preset.hours)))
}
