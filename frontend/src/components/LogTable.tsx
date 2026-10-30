import { ChevronRight } from 'lucide-react'
import { LEVEL_TONE, OUTCOME_TONE } from '../lib/levels'
import { clockTime, shortDate } from '../lib/format'
import type { LogEntry } from '../lib/types'
import { LevelBadge, OutcomeBadge } from './ui'
import { cn } from '../lib/cn'

function railColor(entry: LogEntry): string {
  return entry.log_type === 'app' ? LEVEL_TONE[entry.level].rail : OUTCOME_TONE[entry.outcome].fg
}

/** Dense console table. Each row carries a severity rail on its left edge. */
export function LogTable({
  entries,
  selectedKey,
  onSelect,
  freshKeys,
}: {
  entries: LogEntry[]
  selectedKey?: string | null
  onSelect: (entry: LogEntry) => void
  freshKeys?: Set<string>
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] border-collapse text-left">
        <thead>
          <tr className="border-b border-[var(--color-border-subtle)] font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--color-text-faint)]">
            <th className="w-[132px] py-2.5 pl-5 pr-3 font-normal">Time</th>
            <th className="w-[76px] px-3 font-normal">Level</th>
            <th className="w-[160px] px-3 font-normal">Service</th>
            <th className="px-3 font-normal">Event</th>
            <th className="w-10 px-3" />
          </tr>
        </thead>
        <tbody>
          {entries.map((entry, i) => {
            const key = `${entry.log_type}:${entry.id}`
            const selected = key === selectedKey
            return (
              <tr
                key={key}
                onClick={() => onSelect(entry)}
                onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onSelect(entry))}
                tabIndex={0}
                aria-selected={selected}
                className={cn(
                  'group cursor-pointer border-b border-[var(--color-border-subtle)] align-top transition-colors last:border-0 focus:outline-none',
                  selected ? 'bg-[var(--color-bg-panel)]' : 'hover:bg-[var(--color-bg-panel)] focus-visible:bg-[var(--color-bg-panel)]',
                  freshKeys?.has(key) && 'animate-rise-in',
                )}
                style={{ animationDelay: freshKeys?.has(key) ? `${Math.min(i, 8) * 30}ms` : undefined }}
              >
                <td className="relative py-2.5 pl-5 pr-3">
                  <span
                    aria-hidden
                    className="absolute inset-y-1.5 left-0 w-[3px] rounded-r"
                    style={{ background: railColor(entry), opacity: selected ? 1 : 0.85 }}
                  />
                  <div className="tabular font-mono text-[12px] text-[var(--color-text)]">{clockTime(entry.timestamp)}</div>
                  <div className="font-mono text-[10.5px] text-[var(--color-text-faint)]">{shortDate(entry.timestamp)}</div>
                </td>
                <td className="px-3 py-2.5">
                  {entry.log_type === 'app' ? <LevelBadge level={entry.level} /> : <OutcomeBadge outcome={entry.outcome} />}
                </td>
                <td className="px-3 py-2.5">
                  <div className="truncate font-mono text-[12px] text-[var(--color-text-muted)]">{entry.source_service}</div>
                  <div className="font-mono text-[10.5px] text-[var(--color-text-faint)]">
                    {entry.log_type === 'audit' ? 'audit' : entry.environment}
                  </div>
                </td>
                <td className="max-w-0 px-3 py-2.5">
                  {entry.log_type === 'app' ? (
                    <>
                      <div className="truncate text-[13px]">{entry.message}</div>
                      {entry.trace_id && (
                        <div className="truncate font-mono text-[10.5px] text-[var(--color-text-faint)]">
                          trace {entry.trace_id}
                        </div>
                      )}
                    </>
                  ) : (
                    <>
                      <div className="truncate text-[13px]">
                        <span className="font-mono text-[12px] font-medium text-[var(--color-accent-text)]">{entry.action}</span>{' '}
                        <span className="text-[var(--color-text-muted)]">on</span> {entry.target_resource}
                      </div>
                      <div className="truncate font-mono text-[10.5px] text-[var(--color-text-faint)]">
                        {entry.actor_type.toLowerCase()} {entry.actor_id}
                        {entry.ip_address ? ` · ${entry.ip_address}` : ''}
                      </div>
                    </>
                  )}
                </td>
                <td className="px-3 py-2.5 text-right">
                  <ChevronRight
                    className={cn(
                      'ml-auto size-4 text-[var(--color-text-faint)] transition-transform',
                      selected ? 'translate-x-0.5 text-[var(--color-accent-text)]' : 'opacity-0 group-hover:opacity-100',
                    )}
                  />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
