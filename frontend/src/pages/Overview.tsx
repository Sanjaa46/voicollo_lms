import { useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ArrowUpRight } from 'lucide-react'
import { api } from '../lib/api'
import { LEVELS, LEVEL_TONE, SERIES, type SeriesKey } from '../lib/levels'
import { clockTime, compact, integer, percent, relativeTime, shortDate } from '../lib/format'
import { SeriesLegend, SignalStrip } from '../components/SignalStrip'
import { EmptyState, ErrorBanner, LevelBadge, PageHeader, Panel, PanelHeader, Segmented, Spinner } from '../components/ui'

const WINDOWS = [
  { value: '1', label: '1h', range: '1h' },
  { value: '6', label: '6h', range: '6h' },
  { value: '24', label: '24h', range: '24h' },
  { value: '168', label: '7d', range: '7d' },
  { value: '720', label: '30d', range: '30d' },
]

function Kpi({
  label,
  value,
  sub,
  tone,
  to,
  delay,
}: {
  label: string
  value: string
  sub?: ReactNode
  tone?: string
  to?: string
  delay: number
}) {
  const body = (
    <Panel
      className="group relative h-full animate-rise-in overflow-hidden p-5 transition-colors hover:border-[var(--color-border)]"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="flex items-center justify-between font-mono text-[10.5px] uppercase tracking-[0.16em] text-[var(--color-text-faint)]">
        {label}
        {to && <ArrowUpRight className="size-3.5 opacity-0 transition-opacity group-hover:opacity-100" />}
      </div>
      <div
        className="tabular mt-3 font-display text-[34px] font-medium leading-none tracking-tight"
        style={tone ? { color: tone } : undefined}
      >
        {value}
      </div>
      {sub && <div className="mt-2 text-xs text-[var(--color-text-muted)]">{sub}</div>}
    </Panel>
  )
  return to ? <Link to={to}>{body}</Link> : body
}

export function Overview() {
  const [hours, setHours] = useState('24')
  const [hidden, setHidden] = useState<SeriesKey[]>([])
  const navigate = useNavigate()
  const range = WINDOWS.find((w) => w.value === hours)?.range ?? '24h'

  const { data, error, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['overview', hours],
    queryFn: () => api.overview(Number(hours)),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000,
  })

  const toggle = (key: SeriesKey) =>
    setHidden((h) => (h.includes(key) ? h.filter((k) => k !== key) : [...h, key]))

  return (
    <>
      <PageHeader eyebrow="Overview" title="System signal">
        <Segmented
          label="Time window"
          value={hours}
          onChange={setHours}
          options={WINDOWS.map((w) => ({ value: w.value, label: w.label }))}
        />
      </PageHeader>

      {error ? <ErrorBanner error={error} onRetry={() => void refetch()} /> : null}
      {isLoading && <Spinner label="Loading statistics" />}

      {data && (
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
            <Kpi
              delay={0}
              label="Events"
              value={compact(data.totals.app_logs)}
              to={`/logs?type=app&range=${range}`}
              sub={`${integer(data.totals.app_logs_all_time)} retained in total`}
            />
            <Kpi
              delay={60}
              label="Errors"
              value={compact(data.totals.errors)}
              tone={data.totals.errors ? 'var(--color-danger)' : undefined}
              to={`/logs?level=ERROR,FATAL&range=${range}`}
              sub={
                <>
                  <span className="tabular font-mono">{percent(data.error_rate)}</span> of events
                </>
              }
            />
            <Kpi
              delay={120}
              label="Audit events"
              value={compact(data.totals.audit_logs)}
              to={`/logs?type=audit&range=${range}`}
              sub={
                <>
                  <span
                    className="tabular font-mono"
                    style={{ color: data.outcomes.FAILURE ? 'var(--color-danger)' : undefined }}
                  >
                    {integer(data.outcomes.FAILURE)}
                  </span>{' '}
                  failed
                </>
              }
            />
            <Kpi
              delay={180}
              label="Active services"
              value={String(data.totals.active_services)}
              to="/services"
              sub="sent logs in this window"
            />
          </div>

          <Panel className="animate-rise-in" style={{ animationDelay: '200ms' }}>
            <PanelHeader
              title="Volume"
              hint={`${data.bucket_seconds >= 3600 ? `${data.bucket_seconds / 3600}h` : `${data.bucket_seconds / 60}m`} buckets · click a bar to inspect it`}
              actions={
                <span className="flex items-center gap-1.5 font-mono text-[11px] text-[var(--color-text-faint)]">
                  <span
                    className={`size-1.5 rounded-full bg-[var(--color-amber)] ${isFetching ? 'animate-pulse-live' : ''}`}
                  />
                  {clockTime(data.generated_at).slice(0, 8)}
                </span>
              }
            />
            <div className="px-4 pb-3 pt-4">
              <SignalStrip
                buckets={data.timeline}
                bucketSeconds={data.bucket_seconds}
                height={220}
                hidden={hidden}
                onSelect={(from, to) => navigate(`/logs?range=custom&from=${from}&to=${to}`)}
              />
              <div className="mt-2 pl-9">
                <SeriesLegend hidden={hidden} onToggle={toggle} />
              </div>
            </div>
          </Panel>

          <div className="grid gap-5 lg:grid-cols-[1fr_1.4fr]">
            <Panel className="animate-rise-in" style={{ animationDelay: '260ms' }}>
              <PanelHeader title="Severity mix" hint="Application logs in window" />
              <div className="p-4">
                <LevelMix levels={data.levels} />
              </div>
              <PanelHeader title="Top services" />
              {data.top_services.length ? (
                <ul className="divide-y divide-[var(--color-border-subtle)]">
                  {data.top_services.map((s) => {
                    const max = data.top_services[0].app_logs + data.top_services[0].audit_logs || 1
                    const total = s.app_logs + s.audit_logs
                    return (
                      <li key={s.source_service}>
                        <Link
                          to={`/logs?service=${encodeURIComponent(s.source_service)}&range=${range}`}
                          className="block px-4 py-2.5 hover:bg-[var(--color-bg-panel)]"
                        >
                          <div className="flex items-center justify-between gap-3 text-[13px]">
                            <span className="truncate font-mono">{s.source_service}</span>
                            <span className="tabular shrink-0 font-mono text-xs text-[var(--color-text-muted)]">
                              {integer(total)}
                              {s.errors > 0 && (
                                <span className="ml-2 text-[var(--color-danger)]">{integer(s.errors)} err</span>
                              )}
                            </span>
                          </div>
                          <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-[var(--color-bg-panel)]">
                            <div
                              className="h-full rounded-full bg-[var(--color-amber)]"
                              style={{ width: `${(total / max) * 100}%` }}
                            />
                          </div>
                        </Link>
                      </li>
                    )
                  })}
                </ul>
              ) : (
                <EmptyState title="No traffic in this window" />
              )}
            </Panel>

            <Panel className="animate-rise-in" style={{ animationDelay: '320ms' }}>
              <PanelHeader
                title="Recent errors"
                actions={
                  <Link
                    to={`/logs?level=ERROR,FATAL&range=${range}`}
                    className="text-xs text-[var(--color-accent-text)] hover:underline"
                  >
                    View all
                  </Link>
                }
              />
              {data.recent_errors.length ? (
                <ul className="divide-y divide-[var(--color-border-subtle)]">
                  {data.recent_errors.map((e) => (
                    <li key={e.id}>
                      <Link to={`/logs/app/${e.id}`} className="flex gap-3 px-4 py-3 hover:bg-[var(--color-bg-panel)]">
                        <span
                          className="w-[3px] shrink-0 self-stretch rounded"
                          style={{ background: LEVEL_TONE[e.level].rail }}
                        />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <LevelBadge level={e.level} />
                            <span className="truncate font-mono text-xs text-[var(--color-text-muted)]">
                              {e.source_service}
                            </span>
                            <span
                              className="ml-auto shrink-0 font-mono text-[11px] text-[var(--color-text-faint)]"
                              title={`${shortDate(e.timestamp)} ${clockTime(e.timestamp)}`}
                            >
                              {relativeTime(e.timestamp)}
                            </span>
                          </div>
                          <p className="mt-1 truncate text-[13px]">{e.message}</p>
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState title="No errors" hint="Nothing at ERROR or FATAL in this window." />
              )}
            </Panel>
          </div>
        </div>
      )}
    </>
  )
}

function LevelMix({ levels }: { levels: Record<string, number> }) {
  const total = LEVELS.reduce((sum, l) => sum + levels[l], 0)
  if (!total) return <p className="py-3 text-center text-xs text-[var(--color-text-faint)]">No application logs.</p>
  return (
    <>
      <div className="flex h-3 gap-[2px] overflow-hidden rounded-[4px]" role="img" aria-label="Share of logs by level">
        {LEVELS.filter((l) => levels[l]).map((l) => (
          <div
            key={l}
            title={`${l}: ${integer(levels[l])}`}
            style={{ width: `${(levels[l] / total) * 100}%`, background: SERIES.find((s) => s.key === l.toLowerCase())?.color }}
          />
        ))}
      </div>
      <dl className="mt-4 grid grid-cols-5 gap-2">
        {LEVELS.map((l) => (
          <div key={l}>
            <dt className="font-mono text-[10px] tracking-wide" style={{ color: LEVEL_TONE[l].fg }}>
              {l}
            </dt>
            <dd className="tabular font-mono text-sm">{compact(levels[l])}</dd>
          </div>
        ))}
      </dl>
    </>
  )
}
