import type { LogLevel, Outcome } from './types'

export const LEVELS: LogLevel[] = ['DEBUG', 'INFO', 'WARN', 'ERROR', 'FATAL']
export const OUTCOMES: Outcome[] = ['SUCCESS', 'FAILURE', 'PARTIAL']

/** UI tones (text/badges) — ChatBridge semantic status tokens. */
export const LEVEL_TONE: Record<LogLevel, { fg: string; bg: string; border: string; rail: string }> = {
  DEBUG: {
    fg: 'var(--color-text-faint)',
    bg: 'transparent',
    border: 'var(--color-border)',
    rail: 'var(--color-series-debug)',
  },
  INFO: {
    fg: 'var(--color-info)',
    bg: 'var(--color-info-soft)',
    border: 'var(--color-info-border)',
    rail: 'var(--color-series-info)',
  },
  WARN: {
    fg: 'var(--color-warning)',
    bg: 'var(--color-warning-soft)',
    border: 'var(--color-warning-border)',
    rail: 'var(--color-series-warn)',
  },
  ERROR: {
    fg: 'var(--color-danger)',
    bg: 'var(--color-danger-soft)',
    border: 'var(--color-danger-border)',
    rail: 'var(--color-series-error)',
  },
  FATAL: {
    fg: 'var(--color-fatal)',
    bg: 'var(--color-fatal-soft)',
    border: 'var(--color-fatal-border)',
    rail: 'var(--color-series-fatal)',
  },
}

export const OUTCOME_TONE: Record<Outcome, { fg: string; bg: string; border: string }> = {
  SUCCESS: { fg: 'var(--color-success)', bg: 'var(--color-success-soft)', border: 'var(--color-success-border)' },
  FAILURE: { fg: 'var(--color-danger)', bg: 'var(--color-danger-soft)', border: 'var(--color-danger-border)' },
  PARTIAL: { fg: 'var(--color-warning)', bg: 'var(--color-warning-soft)', border: 'var(--color-warning-border)' },
}

/** Chart series in fixed stacking order (validated palette, see styles.css). */
export const SERIES = [
  { key: 'debug', label: 'Debug', color: 'var(--color-series-debug)' },
  { key: 'info', label: 'Info', color: 'var(--color-series-info)' },
  { key: 'warn', label: 'Warn', color: 'var(--color-series-warn)' },
  { key: 'error', label: 'Error', color: 'var(--color-series-error)' },
  { key: 'fatal', label: 'Fatal', color: 'var(--color-series-fatal)' },
  { key: 'audit', label: 'Audit', color: 'var(--color-series-audit)' },
] as const

export type SeriesKey = (typeof SERIES)[number]['key']
