import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Download, Pause, Play, Search, SlidersHorizontal } from 'lucide-react'
import { api } from '../lib/api'
import { LEVELS, LEVEL_TONE, OUTCOMES, OUTCOME_TONE } from '../lib/levels'
import { RANGE_PRESETS, chartHours, presetStart } from '../lib/ranges'
import { fromLocalInput, fullTimestamp, integer, toLocalInput } from '../lib/format'
import type { LogEntry, LogLevel, LogQuery, LogType, Outcome } from '../lib/types'
import { LogDrawer, type FilterPatch } from '../components/LogDetail'
import { LogTable } from '../components/LogTable'
import { SignalStrip } from '../components/SignalStrip'
import { Dialog } from '../components/Dialog'
import {
  Button,
  Chip,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  Kbd,
  PageHeader,
  Panel,
  Segmented,
  Select,
  Spinner,
} from '../components/ui'
import { cn } from '../lib/cn'

const PAGE_SIZES = [25, 50, 100, 200]
const LIVE_INTERVAL_MS = 5000
const TEXT_FILTERS = [
  { key: 'service', label: 'Service', placeholder: 'billing-api' },
  { key: 'env', label: 'Environment', placeholder: 'production' },
  { key: 'trace', label: 'Trace ID', placeholder: '4bf92f35…', hint: 'app logs only' },
  { key: 'actor', label: 'Actor ID', placeholder: 'user-123', hint: 'audit logs only' },
  { key: 'action', label: 'Action', placeholder: 'USER_LOGIN', hint: 'audit logs only' },
] as const

function list<T extends string>(value: string | null, allowed: readonly T[]): T[] {
  return (value ?? '')
    .split(',')
    .map((v) => v.trim().toUpperCase())
    .filter((v): v is T => (allowed as readonly string[]).includes(v))
}

export function Logs() {
  const [params, setParams] = useSearchParams()
  const searchRef = useRef<HTMLInputElement>(null)
  const [moreOpen, setMoreOpen] = useState(false)
  const [customOpen, setCustomOpen] = useState(false)
  const [exporting, setExporting] = useState<null | 'json' | 'csv'>(null)
  const [exportError, setExportError] = useState<unknown>(null)

  // ---------------------------------------------------------------- URL state
  const type = (params.get('type') as LogType) || 'both'
  const levels = list<LogLevel>(params.get('level'), LEVELS)
  const outcomes = list<Outcome>(params.get('outcome'), OUTCOMES)
  const range = params.get('range') || '24h'
  const page = Math.max(1, Number(params.get('page')) || 1)
  const pageSize = PAGE_SIZES.includes(Number(params.get('size'))) ? Number(params.get('size')) : 50
  const sort = params.get('sort') === 'asc' ? 'asc' : 'desc'
  const live = params.get('live') === '1' && page === 1 && sort === 'desc'
  const selected = params.get('sel')

  const update = useCallback(
    (patch: Record<string, string | null | undefined>, { resetPage = true } = {}) => {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          for (const [k, v] of Object.entries(patch)) {
            if (v === null || v === undefined || v === '') next.delete(k)
            else next.set(k, v)
          }
          if (resetPage && !('page' in patch)) next.delete('page')
          return next
        },
        { replace: true },
      )
    },
    [setParams],
  )

  const [draftQ, setDraftQ] = useState(params.get('q') ?? '')
  useEffect(() => {
    const t = window.setTimeout(() => {
      if ((params.get('q') ?? '') !== draftQ) update({ q: draftQ.trim() || null })
    }, 350)
    return () => window.clearTimeout(t)
  }, [draftQ, params, update])

  const query: Omit<LogQuery, 'start_time'> & { range: string } = {
      range,
      log_type: type,
      level: levels.length ? levels : undefined,
      outcome: outcomes.length ? outcomes : undefined,
      source_service: params.get('service') ? [params.get('service')!] : undefined,
      environment: params.get('env') || undefined,
      trace_id: params.get('trace') || undefined,
      actor_id: params.get('actor') || undefined,
      action: params.get('action') || undefined,
      q: params.get('q') || undefined,
      end_time: range === 'custom' ? params.get('to') || undefined : undefined,
      sort,
      page,
      page_size: pageSize,
  }

  const customFrom = params.get('from') || undefined
  const resolve = (): LogQuery => {
    const { range: r, ...rest } = query
    // Presets slide with time: recomputed on every fetch (important in live mode).
    const start_time = r === 'custom' ? customFrom : presetStart(r)
    return { ...rest, start_time }
  }

  const logs = useQuery({
    queryKey: ['logs', query],
    queryFn: ({ signal }) => api.logs(resolve(), signal),
    placeholderData: keepPreviousData,
    refetchInterval: live ? LIVE_INTERVAL_MS : false,
  })

  const volume = useQuery({
    queryKey: ['overview', chartHours(range)],
    queryFn: () => api.overview(chartHours(range)),
    enabled: range !== 'custom',
    placeholderData: keepPreviousData,
    refetchInterval: live ? LIVE_INTERVAL_MS * 3 : 60_000,
  })

  // Rows that appear for the first time animate in (live tail feel).
  // "Adjust state while rendering" pattern: recompute only when new data lands.
  const [tail, setTail] = useState<{ data?: unknown; seen: Set<string>; fresh: Set<string> }>({
    seen: new Set(),
    fresh: new Set(),
  })
  if (logs.data && logs.data !== tail.data) {
    const seenBefore = tail.seen.size > 5000 ? new Set<string>() : tail.seen
    const seenNow = new Set(seenBefore)
    const freshNow = new Set<string>()
    for (const e of logs.data.data) {
      const key = `${e.log_type}:${e.id}`
      if (seenBefore.size && !seenBefore.has(key)) freshNow.add(key)
      seenNow.add(key)
    }
    setTail({ data: logs.data, seen: seenNow, fresh: freshNow })
  }
  const fresh = tail.fresh

  const rows = useMemo(() => logs.data?.data ?? [], [logs.data])
  const selectedEntry = rows.find((e) => `${e.log_type}:${e.id}` === selected) ?? null
  const [pinned, setPinned] = useState<LogEntry | null>(null)
  const drawerEntry = selectedEntry ?? (pinned && `${pinned.log_type}:${pinned.id}` === selected ? pinned : null)

  const select = useCallback(
    (entry: LogEntry | null) => {
      setPinned(entry)
      update({ sel: entry ? `${entry.log_type}:${entry.id}` : null }, { resetPage: false })
    },
    [update],
  )

  const applyFilter = (patch: FilterPatch) => {
    update({ ...patch, sel: null })
    setPinned(null)
  }

  // ---------------------------------------------------------------- keyboard
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes((e.target as HTMLElement).tagName)
      if (e.key === '/' && !typing) {
        e.preventDefault()
        searchRef.current?.focus()
      } else if (e.key === 'Escape' && selected) {
        select(null)
      } else if (!typing && (e.key === 'j' || e.key === 'k') && rows.length) {
        const index = rows.findIndex((r) => `${r.log_type}:${r.id}` === selected)
        const nextIndex = e.key === 'j' ? Math.min(rows.length - 1, index + 1) : Math.max(0, index - 1)
        select(rows[index === -1 ? 0 : nextIndex])
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [rows, selected, select])

  // ---------------------------------------------------------------- export
  const runExport = async (format: 'json' | 'csv') => {
    setExporting(format)
    setExportError(null)
    try {
      const { page: _p, page_size: _s, ...filters } = resolve()
      void _p
      void _s
      const response = await api.exportLogs({ ...filters, format, limit: 10_000 })
      const blob = await response.blob()
      const disposition = response.headers.get('Content-Disposition') ?? ''
      const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? `lms-logs.${format}`
      const url = URL.createObjectURL(blob)
      const a = Object.assign(document.createElement('a'), { href: url, download: name })
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setExportError(err)
    } finally {
      setExporting(null)
    }
  }

  // ---------------------------------------------------------------- chips
  const chips: { label: string; clear: () => void }[] = []
  for (const f of TEXT_FILTERS) {
    const v = params.get(f.key)
    if (v) chips.push({ label: `${f.key}:${v}`, clear: () => update({ [f.key]: null }) })
  }
  if (params.get('q')) chips.push({ label: `"${params.get('q')}"`, clear: () => (setDraftQ(''), update({ q: null })) })
  if (range === 'custom') {
    const from = params.get('from')
    const to = params.get('to')
    chips.push({
      label: `${from ? fullTimestamp(from).slice(0, 16) : '…'} → ${to ? fullTimestamp(to).slice(0, 16) : 'now'}`,
      clear: () => update({ range: null, from: null, to: null }),
    })
  }

  const total = logs.data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / pageSize))
  const showAudit = type !== 'app'
  const showApp = type !== 'audit'

  return (
    <>
      <PageHeader eyebrow="Logs" title="Explorer">
        <Button
          variant={live ? 'primary' : 'secondary'}
          icon={live ? <Pause className="size-4" /> : <Play className="size-4" />}
          onClick={() => update({ live: live ? null : '1', page: null, sort: null }, { resetPage: false })}
          title="Auto-refresh every 5 seconds"
        >
          {live ? 'Live' : 'Go live'}
        </Button>
        <Button icon={<Download className="size-4" />} loading={exporting === 'csv'} onClick={() => runExport('csv')}>
          CSV
        </Button>
        <Button icon={<Download className="size-4" />} loading={exporting === 'json'} onClick={() => runExport('json')}>
          JSON
        </Button>
      </PageHeader>

      {/* --------------------------------------------------------------- filter bar */}
      <Panel className="mb-4">
        <div className="flex flex-wrap items-center gap-3 p-3">
          <div className="relative min-w-[220px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[var(--color-text-faint)]" />
            <Input
              ref={searchRef}
              value={draftQ}
              onChange={(e) => setDraftQ(e.target.value)}
              placeholder="Search messages, actions, targets…"
              className="pl-9 pr-10 font-mono text-[13px]"
              aria-label="Search logs"
            />
            <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2">
              <Kbd>/</Kbd>
            </span>
          </div>
          <Segmented
            label="Log type"
            value={type}
            onChange={(v) => update({ type: v === 'both' ? null : v })}
            options={[
              { value: 'both', label: 'All' },
              { value: 'app', label: 'App' },
              { value: 'audit', label: 'Audit' },
            ]}
          />
          <Segmented
            label="Time range"
            value={range}
            onChange={(v) => update({ range: v === '24h' ? null : v, from: null, to: null })}
            options={[
              ...RANGE_PRESETS.map((p) => ({ value: p.key, label: p.label })),
              ...(range === 'custom' ? [{ value: 'custom', label: 'Custom' }] : []),
            ]}
          />
          <Button size="sm" variant="ghost" onClick={() => setCustomOpen(true)}>
            Custom…
          </Button>
          <Button
            size="sm"
            variant={moreOpen ? 'secondary' : 'ghost'}
            icon={<SlidersHorizontal className="size-3.5" />}
            onClick={() => setMoreOpen((o) => !o)}
            aria-expanded={moreOpen}
          >
            Filters
          </Button>
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-[var(--color-border-subtle)] px-3 py-2.5">
          {showApp && (
            <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Levels">
              {LEVELS.map((l) => {
                const on = levels.includes(l)
                return (
                  <button
                    key={l}
                    aria-pressed={on}
                    onClick={() => update({ level: (on ? levels.filter((x) => x !== l) : [...levels, l]).join(',') || null })}
                    className="h-6 rounded-[4px] border px-2 font-mono text-[10.5px] font-semibold tracking-wide transition-colors"
                    style={
                      on
                        ? { color: LEVEL_TONE[l].fg, background: LEVEL_TONE[l].bg, borderColor: LEVEL_TONE[l].border }
                        : { color: 'var(--color-text-faint)', borderColor: 'var(--color-border)' }
                    }
                  >
                    {l}
                  </button>
                )
              })}
            </div>
          )}
          {showApp && showAudit && <span className="h-4 w-px bg-[var(--color-border)]" aria-hidden />}
          {showAudit && (
            <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Outcomes">
              {OUTCOMES.map((o) => {
                const on = outcomes.includes(o)
                return (
                  <button
                    key={o}
                    aria-pressed={on}
                    onClick={() =>
                      update({ outcome: (on ? outcomes.filter((x) => x !== o) : [...outcomes, o]).join(',') || null })
                    }
                    className="h-6 rounded-[4px] border px-2 font-mono text-[10.5px] font-semibold tracking-wide transition-colors"
                    style={
                      on
                        ? { color: OUTCOME_TONE[o].fg, background: OUTCOME_TONE[o].bg, borderColor: OUTCOME_TONE[o].border }
                        : { color: 'var(--color-text-faint)', borderColor: 'var(--color-border)' }
                    }
                  >
                    {o}
                  </button>
                )
              })}
            </div>
          )}
          {chips.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              {chips.map((c) => (
                <Chip key={c.label} onRemove={c.clear}>
                  {c.label}
                </Chip>
              ))}
            </div>
          )}
          {(levels.length > 0 || outcomes.length > 0 || chips.length > 0 || type !== 'both') && (
            <button
              className="ml-auto text-xs text-[var(--color-text-faint)] hover:text-[var(--color-text)]"
              onClick={() => {
                setDraftQ('')
                setParams(new URLSearchParams(range !== '24h' ? { range } : {}), { replace: true })
              }}
            >
              Clear all
            </button>
          )}
        </div>

        {moreOpen && (
          <div className="grid animate-fade-in gap-3 border-t border-[var(--color-border-subtle)] p-3 sm:grid-cols-2 lg:grid-cols-5">
            {TEXT_FILTERS.map(({ key, ...f }) => (
              <TextFilter key={key} {...f} value={params.get(key) ?? ''} onCommit={(v) => update({ [key]: v || null })} />
            ))}
          </div>
        )}
      </Panel>

      {exportError ? (
        <div className="mb-4">
          <ErrorBanner error={exportError} />
        </div>
      ) : null}

      {/* --------------------------------------------------------------- volume */}
      {range !== 'custom' && volume.data && (
        <Panel className="mb-4 px-4 pb-1 pt-3">
          <div className="mb-1 flex items-center justify-between font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--color-text-faint)]">
            <span>All services · volume</span>
            <span className="normal-case tracking-normal">click a bar to zoom</span>
          </div>
          <SignalStrip
            buckets={volume.data.timeline}
            bucketSeconds={volume.data.bucket_seconds}
            height={96}
            onSelect={(from, to) => update({ range: 'custom', from, to, live: null })}
          />
        </Panel>
      )}

      {/* --------------------------------------------------------------- results */}
      {logs.error ? <ErrorBanner error={logs.error} onRetry={() => void logs.refetch()} /> : null}

      <Panel className="overflow-hidden">
        <div className="flex items-center justify-between gap-3 border-b border-[var(--color-border-subtle)] px-4 py-2.5 text-xs text-[var(--color-text-muted)]">
          <span className="flex items-center gap-2">
            {live && <span className="size-1.5 animate-pulse-live rounded-full bg-[var(--color-amber)]" />}
            <span className="tabular font-mono text-[var(--color-text)]">{integer(total)}</span> matching entries
            {logs.isFetching && !logs.isLoading && <span className="text-[var(--color-text-faint)]">· refreshing</span>}
          </span>
          <Segmented
            size="sm"
            label="Sort"
            value={sort}
            onChange={(v) => update({ sort: v === 'desc' ? null : v, live: null })}
            options={[
              { value: 'desc', label: 'Newest' },
              { value: 'asc', label: 'Oldest' },
            ]}
          />
        </div>

        {logs.isLoading ? (
          <Spinner label="Querying logs" />
        ) : rows.length ? (
          <div className={cn('transition-opacity', logs.isPlaceholderData && 'opacity-60')}>
            <LogTable entries={rows} selectedKey={selected} onSelect={select} freshKeys={fresh} />
          </div>
        ) : (
          <EmptyState
            title="No logs match"
            hint="Widen the time range or remove a filter. Level and trace filters show application logs only; actor, action and outcome filters show audit logs only."
          />
        )}

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--color-border-subtle)] px-4 py-2.5 text-xs text-[var(--color-text-muted)]">
          <label className="flex items-center gap-2">
            Rows
            <Select
              className="h-7 w-[72px] py-0 text-xs"
              value={pageSize}
              onChange={(e) => update({ size: e.target.value === '50' ? null : e.target.value })}
            >
              {PAGE_SIZES.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </Select>
          </label>
          <div className="flex items-center gap-2">
            <span className="tabular font-mono">
              {page} / {pages}
            </span>
            <Button
              size="sm"
              variant="ghost"
              disabled={page <= 1}
              onClick={() => update({ page: page - 1 === 1 ? null : String(page - 1) }, { resetPage: false })}
              aria-label="Previous page"
            >
              <ChevronLeft className="size-4" />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={!logs.data?.has_next}
              onClick={() => update({ page: String(page + 1), live: null }, { resetPage: false })}
              aria-label="Next page"
            >
              <ChevronRight className="size-4" />
            </Button>
          </div>
          <span className="hidden items-center gap-1.5 text-[var(--color-text-faint)] md:flex">
            <Kbd>j</Kbd>
            <Kbd>k</Kbd> navigate · <Kbd>esc</Kbd> close
          </span>
        </div>
      </Panel>

      {drawerEntry && <LogDrawer entry={drawerEntry} onClose={() => select(null)} onFilter={applyFilter} />}

      <CustomRangeDialog
        open={customOpen}
        onClose={() => setCustomOpen(false)}
        from={params.get('from') ?? presetStart(range)}
        to={params.get('to') ?? undefined}
        onApply={(from, to) => {
          update({ range: 'custom', from, to, live: null })
          setCustomOpen(false)
        }}
      />
    </>
  )
}

function TextFilter({
  label,
  placeholder,
  hint,
  value,
  onCommit,
}: {
  label: string
  placeholder: string
  hint?: string
  value: string
  onCommit: (value: string) => void
}) {
  const [draft, setDraft] = useState(value)
  const [last, setLast] = useState(value)
  if (value !== last) {
    setLast(value)
    setDraft(value)
  }
  return (
    <Field label={label} hint={hint}>
      <Input
        value={draft}
        placeholder={placeholder}
        className="font-mono text-[13px]"
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => draft.trim() !== value && onCommit(draft.trim())}
        onKeyDown={(e) => e.key === 'Enter' && onCommit(draft.trim())}
      />
    </Field>
  )
}

function CustomRangeDialog({
  open,
  onClose,
  from,
  to,
  onApply,
}: {
  open: boolean
  onClose: () => void
  from?: string
  to?: string
  onApply: (from?: string, to?: string) => void
}) {
  const [start, setStart] = useState(toLocalInput(from))
  const [end, setEnd] = useState(toLocalInput(to))
  const [wasOpen, setWasOpen] = useState(open)
  if (open !== wasOpen) {
    setWasOpen(open)
    if (open) {
      setStart(toLocalInput(from))
      setEnd(toLocalInput(to))
    }
  }
  const invalid = Boolean(start && end && new Date(start) > new Date(end))
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Custom time range"
      description="Times are in your local timezone. Leave “to” empty for “now”."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" disabled={invalid || !start} onClick={() => onApply(fromLocalInput(start), fromLocalInput(end))}>
            Apply
          </Button>
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="From">
          <Input type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} />
        </Field>
        <Field label="To" error={invalid ? 'Must be after “from”' : undefined}>
          <Input type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} />
        </Field>
      </div>
    </Dialog>
  )
}
