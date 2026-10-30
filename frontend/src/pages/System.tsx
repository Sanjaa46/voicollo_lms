import type { ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Database, Gauge, HardDrive, Play, Timer } from 'lucide-react'
import { api } from '../lib/api'
import { compact, duration, fullTimestamp, integer, percent, relativeTime } from '../lib/format'
import type { DependencyStatus } from '../lib/types'
import { Button, ErrorBanner, PageHeader, Panel, PanelHeader, Spinner, StatusDot } from '../components/ui'

function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div>
      <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--color-text-faint)]">{label}</div>
      <div className="tabular mt-1.5 font-display text-2xl font-medium tracking-tight">{value}</div>
      {hint && <div className="mt-1 text-xs text-[var(--color-text-muted)]">{hint}</div>}
    </div>
  )
}

function Dependency({ name, icon, status }: { name: string; icon: ReactNode; status: DependencyStatus }) {
  const ok = status.status === 'ok'
  return (
    <Panel className="flex items-start gap-4 p-5">
      <div className="flex size-10 items-center justify-center rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-panel)] text-[var(--color-text-muted)]">
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">{name}</h3>
          <StatusDot ok={ok} live label={ok ? 'operational' : 'unreachable'} />
        </div>
        <div className="tabular mt-1 font-mono text-xs text-[var(--color-text-muted)]">
          {status.latency_ms != null ? `${status.latency_ms.toFixed(1)} ms round-trip` : '—'}
        </div>
        {status.detail && <p className="mt-2 break-words font-mono text-[11px] text-[var(--color-danger)]">{status.detail}</p>}
      </div>
    </Panel>
  )
}

export function System() {
  const queryClient = useQueryClient()
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ['system'],
    queryFn: api.systemStatus,
    refetchInterval: 15_000,
  })
  const run = useMutation({
    mutationFn: api.runRetention,
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['system'] }),
  })

  return (
    <>
      <PageHeader eyebrow="System" title="Health & operations" />
      {isLoading && <Spinner />}
      {error ? <ErrorBanner error={error} onRetry={() => void refetch()} /> : null}

      {data && (
        <div className="space-y-5">
          <div className="grid gap-4 md:grid-cols-3">
            <Dependency name="MariaDB" icon={<Database className="size-5" />} status={data.health.database} />
            <Dependency name="Redis" icon={<HardDrive className="size-5" />} status={data.health.cache} />
            <Panel className="flex items-start gap-4 p-5">
              <div className="flex size-10 items-center justify-center rounded-[var(--radius-md)] bg-[var(--color-amber)] text-[var(--color-primary-foreground)]">
                <Gauge className="size-5" />
              </div>
              <div className="min-w-0">
                <h3 className="text-sm font-semibold">LMS v{data.version.version}</h3>
                <div className="mt-1 font-mono text-xs text-[var(--color-text-muted)]">
                  {data.version.environment} · {data.version.git_sha.slice(0, 7)}
                </div>
                <div className="font-mono text-xs text-[var(--color-text-faint)]">
                  up {duration(data.health.uptime_seconds)} · built {data.version.build_date}
                </div>
              </div>
            </Panel>
          </div>

          <Panel>
            <PanelHeader
              title="Throughput"
              hint={data.metrics.since ? `Counters since ${fullTimestamp(data.metrics.since)}` : 'Counters are stored in Redis'}
            />
            <div className="grid gap-6 p-5 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Ingested" value={compact(data.metrics.ingestion_total)} hint={`${integer(data.rate_limit_per_minute)}/min per service limit`} />
              <Stat label="Queries" value={compact(data.metrics.query_total)} />
              <Stat
                label="Cache hit ratio"
                value={percent(data.metrics.cache_hit_ratio)}
                hint={`${integer(data.metrics.cache_hits)} hits · ${integer(data.metrics.cache_misses)} misses`}
              />
              <Stat
                label="Errors"
                value={compact(Object.values(data.metrics.error_total).reduce((a, b) => a + b, 0))}
                hint="API errors by code below"
              />
            </div>
            {Object.keys(data.metrics.error_total).length > 0 && (
              <div className="border-t border-[var(--color-border-subtle)] px-5 py-3">
                <div className="flex flex-wrap gap-2">
                  {Object.entries(data.metrics.error_total)
                    .sort((a, b) => b[1] - a[1])
                    .map(([code, count]) => (
                      <span
                        key={code}
                        className="inline-flex items-center gap-2 rounded-[4px] border border-[var(--color-border)] px-2 py-0.5 font-mono text-[11px]"
                      >
                        <span className="text-[var(--color-text-muted)]">{code}</span>
                        <span className="tabular">{integer(count)}</span>
                      </span>
                    ))}
                </div>
              </div>
            )}
          </Panel>

          <Panel>
            <PanelHeader
              title="Retention"
              hint={
                data.retention.policy.enabled
                  ? `Daily at ${data.retention.policy.schedule} (${data.retention.policy.timezone})`
                  : 'Scheduled purge is disabled'
              }
              actions={
                <Button
                  size="sm"
                  icon={<Play className="size-3.5" />}
                  loading={run.isPending || data.retention.running}
                  onClick={() => run.mutate()}
                >
                  Run now
                </Button>
              }
            />
            <div className="grid gap-6 p-5 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="App logs kept" value={`${data.retention.policy.app_log_retention_days}d`} hint="by event time" />
              <Stat label="Audit logs kept" value={`${data.retention.policy.audit_log_retention_days}d`} hint="by ingest time" />
              <Stat
                label="Last run"
                value={data.retention.last_run ? relativeTime(data.retention.last_run.started_at) : 'never'}
                hint={
                  data.retention.last_run && (
                    <span style={{ color: data.retention.last_run.status === 'FAILURE' ? 'var(--color-danger)' : undefined }}>
                      {data.retention.last_run.status.toLowerCase()} · {data.retention.last_run.trigger} ·{' '}
                      {data.retention.last_run.duration_seconds.toFixed(2)}s
                    </span>
                  )
                }
              />
              <Stat
                label="Last purge"
                value={
                  data.retention.last_run
                    ? compact(data.retention.last_run.deleted_app_logs + data.retention.last_run.deleted_audit_logs)
                    : '—'
                }
                hint={
                  data.retention.last_run
                    ? `${integer(data.retention.last_run.deleted_app_logs)} app · ${integer(data.retention.last_run.deleted_audit_logs)} audit`
                    : undefined
                }
              />
            </div>
            {(data.retention.policy.next_run_at || run.error || data.retention.last_run?.error) && (
              <div className="space-y-2 border-t border-[var(--color-border-subtle)] px-5 py-3 text-xs text-[var(--color-text-muted)]">
                {data.retention.policy.next_run_at && (
                  <p className="flex items-center gap-2">
                    <Timer className="size-3.5" /> Next run {fullTimestamp(data.retention.policy.next_run_at)}
                  </p>
                )}
                {data.retention.last_run?.error && (
                  <p className="font-mono text-[var(--color-danger)]">{data.retention.last_run.error}</p>
                )}
                {run.error ? <ErrorBanner error={run.error} /> : null}
              </div>
            )}
          </Panel>

          <Panel className="p-5">
            <h3 className="text-sm font-semibold">Ingest security</h3>
            <p className="mt-1 text-xs leading-relaxed text-[var(--color-text-muted)]">
              Producers sign every request with HMAC-SHA256 over <code className="font-mono">timestamp + "." + body</code>.
              Timestamps older than {data.signature_tolerance_seconds}s are rejected and each signature is accepted once
              (replays get <code className="font-mono">409 DUPLICATE_REQUEST</code>). Audit logs cannot be modified or
              deleted through the API.
            </p>
          </Panel>
        </div>
      )}
    </>
  )
}
