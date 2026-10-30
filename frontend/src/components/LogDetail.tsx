import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ExternalLink, Filter, X } from 'lucide-react'
import { fullTimestamp, relativeTime, timezoneLabel } from '../lib/format'
import type { LogEntry } from '../lib/types'
import { JsonView } from './JsonView'
import { CopyButton, IconButton, LevelBadge, OutcomeBadge } from './ui'

export type FilterPatch = Partial<Record<'service' | 'trace' | 'actor' | 'action' | 'env', string>>

function Row({ label, children, copy }: { label: string; children: ReactNode; copy?: string }) {
  return (
    <div className="grid grid-cols-[112px_1fr_auto] items-start gap-3 border-b border-[var(--color-border-subtle)] py-2 last:border-0">
      <dt className="pt-0.5 font-mono text-[10.5px] uppercase tracking-[0.12em] text-[var(--color-text-faint)]">{label}</dt>
      <dd className="min-w-0 break-words text-[13px]">{children}</dd>
      <div className="-my-1">{copy && <CopyButton value={copy} label={`Copy ${label}`} />}</div>
    </div>
  )
}

function FilterLink({ onFilter, patch, children }: { onFilter?: (p: FilterPatch) => void; patch: FilterPatch; children: ReactNode }) {
  if (!onFilter) return <>{children}</>
  return (
    <button
      onClick={() => onFilter(patch)}
      className="group inline-flex items-center gap-1.5 text-left hover:text-[var(--color-accent-text)]"
      title="Filter by this value"
    >
      {children}
      <Filter className="size-3 opacity-0 transition-opacity group-hover:opacity-70" />
    </button>
  )
}

export function LogDetailBody({ entry, onFilter }: { entry: LogEntry; onFilter?: (p: FilterPatch) => void }) {
  const mono = 'font-mono text-[12.5px]'
  return (
    <div className="space-y-5">
      {entry.log_type === 'app' ? (
        <div className="whitespace-pre-wrap break-words rounded-[var(--radius-md)] border border-[var(--color-border-subtle)] bg-[var(--color-bg)] p-3.5 font-mono text-[13px] leading-relaxed">
          {entry.message}
        </div>
      ) : (
        <div className="rounded-[var(--radius-md)] border border-[var(--color-border-subtle)] bg-[var(--color-bg)] p-3.5">
          <div className="font-mono text-[15px] font-medium text-[var(--color-accent-text)]">{entry.action}</div>
          <div className="mt-1 text-sm text-[var(--color-text-muted)]">
            {entry.actor_type.toLowerCase()} <span className="text-[var(--color-text)]">{entry.actor_id}</span> on{' '}
            <span className="text-[var(--color-text)]">{entry.target_resource}</span>
          </div>
        </div>
      )}

      <dl>
        <Row label="Time" copy={entry.timestamp}>
          <span className={mono}>{fullTimestamp(entry.timestamp)}</span>{' '}
          <span className="text-xs text-[var(--color-text-faint)]">
            {timezoneLabel} · {relativeTime(entry.timestamp)}
          </span>
        </Row>
        <Row label="Ingested">
          <span className={mono}>{fullTimestamp(entry.ingested_at)}</span>
        </Row>
        <Row label="Service" copy={entry.source_service}>
          <FilterLink onFilter={onFilter} patch={{ service: entry.source_service }}>
            <span className={mono}>{entry.source_service}</span>
          </FilterLink>
        </Row>
        {entry.environment && (
          <Row label="Environment">
            <FilterLink onFilter={onFilter} patch={{ env: entry.environment }}>
              <span className={mono}>{entry.environment}</span>
            </FilterLink>
          </Row>
        )}
        {entry.log_type === 'app' ? (
          <>
            <Row label="Level">
              <LevelBadge level={entry.level} />
            </Row>
            {entry.trace_id && (
              <Row label="Trace" copy={entry.trace_id}>
                <FilterLink onFilter={onFilter} patch={{ trace: entry.trace_id }}>
                  <span className={mono}>{entry.trace_id}</span>
                </FilterLink>
              </Row>
            )}
          </>
        ) : (
          <>
            <Row label="Outcome">
              <OutcomeBadge outcome={entry.outcome} />
            </Row>
            <Row label="Actor" copy={entry.actor_id}>
              <FilterLink onFilter={onFilter} patch={{ actor: entry.actor_id }}>
                <span className={mono}>{entry.actor_id}</span>
              </FilterLink>{' '}
              <span className="text-xs text-[var(--color-text-faint)]">{entry.actor_type}</span>
            </Row>
            <Row label="Action">
              <FilterLink onFilter={onFilter} patch={{ action: entry.action }}>
                <span className={mono}>{entry.action}</span>
              </FilterLink>
            </Row>
            <Row label="Target" copy={entry.target_resource}>
              <span className={mono}>{entry.target_resource}</span>
            </Row>
            {entry.ip_address && (
              <Row label="IP address" copy={entry.ip_address}>
                <span className={mono}>{entry.ip_address}</span>
              </Row>
            )}
          </>
        )}
        <Row label="ID" copy={String(entry.id)}>
          <span className={mono}>
            {entry.log_type}#{entry.id}
          </span>
        </Row>
      </dl>

      {(() => {
        const payload = entry.log_type === 'app' ? entry.context_json : entry.detail_json
        if (!payload) return null
        return (
          <section>
            <div className="mb-2 flex items-center justify-between">
              <h3 className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-[var(--color-text-faint)]">
                {entry.log_type === 'app' ? 'context_json' : 'detail_json'}
              </h3>
              <CopyButton value={JSON.stringify(payload, null, 2)} label="Copy JSON" />
            </div>
            <JsonView value={payload} />
          </section>
        )
      })()}
    </div>
  )
}

export function LogDrawer({
  entry,
  onClose,
  onFilter,
}: {
  entry: LogEntry
  onClose: () => void
  onFilter: (p: FilterPatch) => void
}) {
  return (
    <aside
      aria-label="Log details"
      className="fixed inset-y-0 right-0 z-40 flex w-full max-w-[520px] animate-drawer-in flex-col border-l border-[var(--color-border)] bg-[var(--color-bg-raised)] shadow-[var(--shadow-lg)]"
    >
      <div className="flex h-14 items-center justify-between gap-3 border-b border-[var(--color-border-subtle)] px-5">
        <div className="font-mono text-xs text-[var(--color-text-muted)]">
          {entry.log_type === 'app' ? 'application' : 'audit'} log{' '}
          <span className="text-[var(--color-text)]">#{entry.id}</span>
        </div>
        <div className="flex items-center gap-1">
          <CopyButton value={JSON.stringify(entry, null, 2)} label="Copy entry as JSON" />
          <Link
            to={`/logs/${entry.log_type}/${entry.id}`}
            className="inline-flex size-8 items-center justify-center rounded-[var(--radius-sm)] text-[var(--color-text-muted)] hover:bg-[var(--color-bg-panel-hover)] hover:text-[var(--color-text)]"
            title="Open as page"
            aria-label="Open as page"
          >
            <ExternalLink className="size-3.5" />
          </Link>
          <IconButton label="Close (Esc)" onClick={onClose}>
            <X className="size-4" />
          </IconButton>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto px-5 py-5">
        <LogDetailBody entry={entry} onFilter={onFilter} />
      </div>
    </aside>
  )
}
