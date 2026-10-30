import { useEffect, useRef, useState, type ButtonHTMLAttributes, type ComponentProps, type ReactNode } from 'react'
import { AlertTriangle, Check, Copy, Inbox, Loader2, X } from 'lucide-react'
import { LEVEL_TONE, OUTCOME_TONE } from '../lib/levels'
import type { LogLevel, Outcome } from '../lib/types'
import { ApiError } from '../lib/api'
import { cn } from '../lib/cn'

// ------------------------------------------------------------------ buttons
type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'

const VARIANTS: Record<Variant, string> = {
  primary:
    'bg-[var(--color-primary)] text-[var(--color-primary-foreground)] hover:brightness-110 shadow-[var(--shadow-sm)] font-semibold',
  secondary:
    'bg-[var(--color-bg-panel)] text-[var(--color-text)] border border-[var(--color-border)] hover:bg-[var(--color-bg-panel-hover)]',
  ghost: 'text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg-panel-hover)]',
  danger:
    'bg-[var(--color-danger-soft)] text-[var(--color-danger)] border border-[var(--color-danger-border)] hover:brightness-125',
}

export function Button({
  variant = 'secondary',
  size = 'md',
  loading,
  icon,
  className,
  children,
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant
  size?: 'sm' | 'md'
  loading?: boolean
  icon?: ReactNode
}) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={cn(
        'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[var(--radius-sm)] transition-[background,filter,color] duration-[var(--duration-fast)] disabled:cursor-not-allowed disabled:opacity-50',
        size === 'sm' ? 'h-8 px-2.5 text-xs' : 'h-9 px-3.5 text-sm',
        VARIANTS[variant],
        className,
      )}
    >
      {loading ? <Loader2 className="size-4 animate-spin" /> : icon}
      {children}
    </button>
  )
}

export function IconButton({ label, className, children, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button
      {...rest}
      aria-label={label}
      title={label}
      className={cn(
        'inline-flex size-8 items-center justify-center rounded-[var(--radius-sm)] text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-bg-panel-hover)] hover:text-[var(--color-text)]',
        className,
      )}
    >
      {children}
    </button>
  )
}

// ------------------------------------------------------------------ surfaces
export function Panel({ className, children, ...rest }: ComponentProps<'div'>) {
  return (
    <div
      {...rest}
      className={cn(
        'rounded-[var(--radius-lg)] border border-[var(--color-border-subtle)] bg-[var(--color-bg-raised)]',
        className,
      )}
    >
      {children}
    </div>
  )
}

export function PanelHeader({ title, hint, actions }: { title: ReactNode; hint?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-[var(--color-border-subtle)] px-4 py-3">
      <div className="min-w-0">
        <h2 className="text-[13px] font-semibold tracking-tight">{title}</h2>
        {hint && <p className="text-xs text-[var(--color-text-faint)]">{hint}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  )
}

export function PageHeader({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {eyebrow && (
          <div className="mb-1.5 font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--color-accent-text)]">
            {eyebrow}
          </div>
        )}
        <h1 className="font-display text-[26px] font-medium leading-tight tracking-tight">{title}</h1>
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  )
}

// ------------------------------------------------------------------ forms
const fieldBase =
  'w-full rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-bg)] px-3 text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-faint)] transition-colors focus:border-[var(--color-amber-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-amber-soft)]'

export function Input({ className, ...rest }: ComponentProps<'input'>) {
  return <input {...rest} className={cn(fieldBase, 'h-9', className)} />
}

export function Textarea({ className, ...rest }: ComponentProps<'textarea'>) {
  return <textarea {...rest} className={cn(fieldBase, 'min-h-20 py-2', className)} />
}

export function Select({ className, children, ...rest }: ComponentProps<'select'>) {
  return (
    <select {...rest} className={cn(fieldBase, 'h-9 pr-8', className)}>
      {children}
    </select>
  )
}

export function Field({ label, hint, error, children }: { label: string; hint?: string; error?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-[var(--color-text-muted)]">{label}</span>
      {children}
      {error ? (
        <span className="mt-1 block text-xs text-[var(--color-danger)]">{error}</span>
      ) : (
        hint && <span className="mt-1 block text-xs text-[var(--color-text-faint)]">{hint}</span>
      )}
    </label>
  )
}

/** Segmented control — used for log type, time range, sort. */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  size = 'md',
  label,
}: {
  value: T
  options: { value: T; label: ReactNode }[]
  onChange: (value: T) => void
  size?: 'sm' | 'md'
  label: string
}) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="inline-flex rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-bg)] p-0.5"
    >
      {options.map((opt) => {
        const active = opt.value === value
        return (
          <button
            key={opt.value}
            role="radio"
            aria-checked={active}
            onClick={() => onChange(opt.value)}
            className={cn(
              'rounded-[5px] px-2.5 font-mono transition-colors',
              size === 'sm' ? 'h-6 text-[11px]' : 'h-7 text-xs',
              active
                ? 'bg-[var(--color-bg-panel-hover)] text-[var(--color-text)] shadow-[var(--shadow-sm)]'
                : 'text-[var(--color-text-faint)] hover:text-[var(--color-text)]',
            )}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}

// ------------------------------------------------------------------ badges
export function LevelBadge({ level }: { level: LogLevel }) {
  const tone = LEVEL_TONE[level]
  return (
    <span
      className="inline-flex h-5 min-w-[46px] items-center justify-center rounded-[4px] border px-1.5 font-mono text-[10.5px] font-semibold tracking-wide"
      style={{ color: tone.fg, background: tone.bg, borderColor: tone.border }}
    >
      {level}
    </span>
  )
}

export function OutcomeBadge({ outcome }: { outcome: Outcome }) {
  const tone = OUTCOME_TONE[outcome]
  return (
    <span
      className="inline-flex h-5 items-center justify-center rounded-[4px] border px-1.5 font-mono text-[10.5px] font-semibold tracking-wide"
      style={{ color: tone.fg, background: tone.bg, borderColor: tone.border }}
    >
      {outcome}
    </span>
  )
}

export function StatusDot({ ok, live, label }: { ok: boolean; live?: boolean; label?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className={cn('size-2 rounded-full', live && ok && 'animate-pulse-live')}
        style={{ background: ok ? 'var(--color-success)' : 'var(--color-danger)' }}
      />
      {label && <span className="text-xs text-[var(--color-text-muted)]">{label}</span>}
    </span>
  )
}

export function Chip({ children, onRemove }: { children: ReactNode; onRemove?: () => void }) {
  return (
    <span className="inline-flex h-6 items-center gap-1 rounded-full border border-[var(--color-amber-border)] bg-[var(--color-amber-soft)] pl-2.5 pr-1 font-mono text-[11px] text-[var(--color-accent-text)]">
      {children}
      {onRemove && (
        <button onClick={onRemove} aria-label="Remove filter" className="rounded-full p-0.5 hover:bg-[var(--color-amber-border)]">
          <X className="size-3" />
        </button>
      )}
    </span>
  )
}

// ------------------------------------------------------------------ feedback
export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-sm text-[var(--color-text-faint)]">
      <Loader2 className="size-4 animate-spin text-[var(--color-amber)]" />
      {label}
    </div>
  )
}

export function EmptyState({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-14 text-center">
      <div className="mb-1 flex size-10 items-center justify-center rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-panel)]">
        <Inbox className="size-5 text-[var(--color-text-faint)]" />
      </div>
      <p className="text-sm font-medium">{title}</p>
      {hint && <p className="max-w-sm text-xs text-[var(--color-text-faint)]">{hint}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}

export function ErrorBanner({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : 'Something went wrong.'
  const requestId = error instanceof ApiError ? error.requestId : undefined
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-[var(--radius-md)] border border-[var(--color-danger-border)] bg-[var(--color-danger-soft)] px-4 py-3 text-sm"
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-[var(--color-danger)]" />
      <div className="min-w-0 flex-1">
        <p className="text-[var(--color-text)]">{message}</p>
        {requestId && <p className="mt-0.5 font-mono text-[11px] text-[var(--color-text-faint)]">request {requestId}</p>}
      </div>
      {onRetry && (
        <Button size="sm" variant="ghost" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  )
}

export function CopyButton({ value, label = 'Copy' }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false)
  const timer = useRef<number | undefined>(undefined)
  useEffect(() => () => window.clearTimeout(timer.current), [])
  return (
    <IconButton
      label={copied ? 'Copied' : label}
      onClick={async (e) => {
        e.stopPropagation()
        try {
          await navigator.clipboard.writeText(value)
          setCopied(true)
          timer.current = window.setTimeout(() => setCopied(false), 1400)
        } catch {
          /* clipboard blocked */
        }
      }}
    >
      {copied ? <Check className="size-3.5 text-[var(--color-success)]" /> : <Copy className="size-3.5" />}
    </IconButton>
  )
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="inline-flex h-5 min-w-5 items-center justify-center rounded-[4px] border border-[var(--color-border)] bg-[var(--color-bg-panel)] px-1 font-mono text-[10px] text-[var(--color-text-faint)]">
      {children}
    </kbd>
  )
}
