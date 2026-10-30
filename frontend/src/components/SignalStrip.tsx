import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { SERIES, type SeriesKey } from '../lib/levels'
import { clockTime, compact, integer, shortDate } from '../lib/format'
import type { TimeBucket } from '../lib/types'

/**
 * Stacked volume histogram ("signal strip").
 * Marks follow the dataviz spec: fixed series order, 2px surface gaps between
 * stacked segments, rounded top only, recessive grid, hover tooltip with every
 * series value, legend always shown (identity never color-alone).
 */
export function SignalStrip({
  buckets,
  bucketSeconds,
  height = 180,
  hidden = [],
  onSelect,
}: {
  buckets: TimeBucket[]
  bucketSeconds: number
  height?: number
  hidden?: SeriesKey[]
  onSelect?: (startIso: string, endIso: string) => void
}) {
  const wrap = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(800)
  const [hover, setHover] = useState<number | null>(null)

  useLayoutEffect(() => {
    const el = wrap.current
    if (!el) return
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(240, entry.contentRect.width)))
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const series = SERIES.filter((s) => !hidden.includes(s.key))
  const totals = useMemo(
    () => buckets.map((b) => series.reduce((sum, s) => sum + b[s.key], 0)),
    [buckets, series],
  )
  const max = Math.max(1, ...totals)
  const niceMax = niceCeil(max)

  const padTop = 8
  const padBottom = 22
  const padLeft = 36
  const plotH = height - padTop - padBottom
  const plotW = width - padLeft
  const slot = plotW / Math.max(1, buckets.length)
  const barW = Math.max(2, Math.min(28, slot - Math.max(1, slot * 0.22)))
  const y = (v: number) => padTop + plotH - (v / niceMax) * plotH

  const multiDay = bucketSeconds >= 3600 * 3 || buckets.length * bucketSeconds > 86400
  const minTickGap = multiDay ? 130 : 70
  const tickEvery = Math.max(1, Math.ceil(buckets.length / Math.max(2, Math.floor(plotW / minTickGap))))

  const hovered = hover !== null ? buckets[hover] : null

  return (
    <div ref={wrap} className="relative select-none">
      <svg
        width={width}
        height={height}
        role="img"
        aria-label={`Log volume, ${buckets.length} buckets, peak ${max} events`}
        onMouseLeave={() => setHover(null)}
      >
        {[0, 0.5, 1].map((f) => (
          <g key={f}>
            <line
              x1={padLeft}
              x2={width}
              y1={y(niceMax * f)}
              y2={y(niceMax * f)}
              stroke="var(--color-border-subtle)"
              strokeDasharray={f === 0 ? undefined : '2 4'}
            />
            <text
              x={padLeft - 8}
              y={y(niceMax * f) + 3}
              textAnchor="end"
              className="fill-[var(--color-text-faint)] font-mono text-[10px]"
            >
              {compact(niceMax * f)}
            </text>
          </g>
        ))}

        {buckets.map((bucket, i) => {
          const x = padLeft + i * slot + (slot - barW) / 2
          let acc = 0
          const segments = series
            .map((s) => ({ key: s.key, color: s.color, value: bucket[s.key] }))
            .filter((s) => s.value > 0)
          const dim = hover !== null && hover !== i
          return (
            <g key={bucket.start} opacity={dim ? 0.45 : 1} style={{ transition: 'opacity 120ms' }}>
              {segments.map((seg, idx) => {
                const top = y(acc + seg.value)
                const bottom = y(acc)
                acc += seg.value
                const isTop = idx === segments.length - 1
                // 2px surface gap between stacked segments.
                const h = Math.max(1, bottom - top - (idx > 0 ? 2 : 0))
                return (
                  <rect
                    key={seg.key}
                    x={x}
                    y={top}
                    width={barW}
                    height={h}
                    rx={isTop ? Math.min(3, barW / 2) : 0}
                    fill={seg.color}
                  />
                )
              })}
              {/* hit target: whole column, wider than the mark */}
              <rect
                x={padLeft + i * slot}
                y={padTop}
                width={slot}
                height={plotH}
                fill="transparent"
                className={onSelect ? 'cursor-zoom-in' : undefined}
                onMouseEnter={() => setHover(i)}
                onClick={() => {
                  if (!onSelect) return
                  const start = new Date(bucket.start)
                  onSelect(start.toISOString(), new Date(start.getTime() + bucketSeconds * 1000).toISOString())
                }}
              />
            </g>
          )
        })}

        {buckets.map((bucket, i) =>
          i % tickEvery === 0 ? (
            <text
              key={bucket.start}
              x={padLeft + i * slot + slot / 2}
              y={height - 6}
              textAnchor="middle"
              className="fill-[var(--color-text-faint)] font-mono text-[10px]"
            >
              {multiDay ? `${shortDate(bucket.start)} ${clockTime(bucket.start).slice(0, 5)}` : clockTime(bucket.start).slice(0, 5)}
            </text>
          ) : null,
        )}
      </svg>

      {hovered && hover !== null && (
        <div
          className="pointer-events-none absolute top-0 z-10 w-44 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-panel)] p-2.5 shadow-[var(--shadow-md)]"
          style={{
            left: Math.min(width - 184, Math.max(0, padLeft + hover * slot + slot / 2 - 88)),
          }}
        >
          <div className="mb-1.5 font-mono text-[11px] text-[var(--color-text-muted)]">
            {shortDate(hovered.start)} {clockTime(hovered.start).slice(0, 5)}
          </div>
          {[...series].reverse().map((s) => (
            <div key={s.key} className="flex items-center justify-between gap-3 text-xs">
              <span className="flex items-center gap-1.5 text-[var(--color-text-muted)]">
                <span className="size-2 rounded-[2px]" style={{ background: s.color }} />
                {s.label}
              </span>
              <span className="tabular font-mono text-[var(--color-text)]">{integer(hovered[s.key])}</span>
            </div>
          ))}
          <div className="mt-1.5 flex justify-between border-t border-[var(--color-border-subtle)] pt-1.5 text-xs">
            <span className="text-[var(--color-text-faint)]">Total</span>
            <span className="tabular font-mono">{integer(totals[hover])}</span>
          </div>
        </div>
      )}
    </div>
  )
}

export function SeriesLegend({
  hidden = [],
  onToggle,
}: {
  hidden?: SeriesKey[]
  onToggle?: (key: SeriesKey) => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      {SERIES.map((s) => {
        const off = hidden.includes(s.key)
        return (
          <button
            key={s.key}
            type="button"
            onClick={() => onToggle?.(s.key)}
            disabled={!onToggle}
            aria-pressed={!off}
            className="flex items-center gap-1.5 text-xs text-[var(--color-text-muted)] transition-opacity enabled:hover:text-[var(--color-text)] disabled:cursor-default"
            style={{ opacity: off ? 0.4 : 1 }}
          >
            <span className="size-2.5 rounded-[3px]" style={{ background: s.color }} />
            {s.label}
          </button>
        )
      })}
    </div>
  )
}

function niceCeil(value: number): number {
  const exp = Math.pow(10, Math.floor(Math.log10(value)))
  const n = value / exp
  const nice = n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10
  return nice * exp
}
