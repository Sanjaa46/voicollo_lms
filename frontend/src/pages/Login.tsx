import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Lock } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Logo } from '../components/Shell'
import { Button, ErrorBanner } from '../components/ui'

const TAIL = [
  ['INFO', 'billing-api', 'payment captured order=8812 amount=129000'],
  ['WARN', 'auth-svc', 'token refresh retried attempt=2'],
  ['INFO', 'chatbridge', 'webhook delivered channel=messenger 182ms'],
  ['ERROR', 'billing-api', 'upstream timeout after 30000ms'],
  ['INFO', 'inventory', 'stock synced sku=AB-1029 qty=14'],
  ['AUDIT', 'auth-svc', 'USER_LOGIN success actor=u-4413'],
  ['DEBUG', 'chatbridge', 'queue depth=3 workers=4'],
  ['INFO', 'billing-api', 'invoice issued inv=2026-1043'],
] as const

const TONE: Record<string, string> = {
  INFO: 'var(--color-series-info)',
  WARN: 'var(--color-series-warn)',
  ERROR: 'var(--color-series-error)',
  DEBUG: 'var(--color-series-debug)',
  AUDIT: 'var(--color-series-audit)',
}

function DecorativeTail() {
  return (
    <div aria-hidden className="space-y-2 font-mono text-[12px]">
      {TAIL.map(([level, service, msg], i) => (
        <div
          key={i}
          className="flex animate-rise-in items-center gap-3 opacity-0"
          style={{ animationDelay: `${300 + i * 140}ms` }}
        >
          <span className="w-[3px] self-stretch rounded" style={{ background: TONE[level] }} />
          <span className="w-12 text-[10.5px] font-semibold" style={{ color: TONE[level] }}>
            {level}
          </span>
          <span className="w-24 truncate text-[var(--color-text-faint)]">{service}</span>
          <span className="truncate text-[var(--color-text-muted)]">{msg}</span>
        </div>
      ))}
      <div className="flex items-center gap-2 pt-2 text-[11px] text-[var(--color-text-faint)]">
        <span className="size-1.5 animate-pulse-live rounded-full bg-[var(--color-amber)]" /> tailing
      </div>
    </div>
  )
}

export function Login() {
  const { session } = useAuth()
  const [redirecting, setRedirecting] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const version = useQuery({ queryKey: ['version'], queryFn: api.version, staleTime: Infinity })

  if (session) return <Navigate to="/" replace />

  const start = async () => {
    setRedirecting(true)
    setError(null)
    try {
      const { authorization_url } = await api.loginUrl()
      window.location.assign(authorization_url)
    } catch (err) {
      setError(err)
      setRedirecting(false)
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.15fr_1fr]">
      <section className="console-grid relative hidden flex-col justify-between overflow-hidden border-r border-[var(--color-border-subtle)] p-12 lg:flex">
        <div
          aria-hidden
          className="pointer-events-none absolute -left-40 -top-40 size-[520px] rounded-full opacity-[0.10] blur-3xl"
          style={{ background: 'var(--color-amber)' }}
        />
        <div className="relative flex items-center gap-3">
          <Logo size={32} />
          <span className="font-display text-lg font-medium tracking-tight">Voicollo</span>
        </div>

        <div className="relative max-w-xl">
          <p className="mb-4 font-mono text-[11px] uppercase tracking-[0.22em] text-[var(--color-accent-text)]">
            Log management system
          </p>
          <h1 className="font-display text-[44px] font-medium leading-[1.05] tracking-tight">
            Every service.
            <br />
            One signal.
          </h1>
          <p className="mt-5 max-w-md text-[15px] leading-relaxed text-[var(--color-text-muted)]">
            Application and audit logs from all of your services — searchable, retained on policy, and
            tamper-proof where it matters.
          </p>
          <div className="mt-10 rounded-[var(--radius-lg)] border border-[var(--color-border-subtle)] bg-[color-mix(in_srgb,var(--color-bg-raised)_80%,transparent)] p-5 backdrop-blur">
            <DecorativeTail />
          </div>
        </div>

        <div className="relative font-mono text-[11px] text-[var(--color-text-faint)]">
          {version.data ? `v${version.data.version}` : ''} · single-operator console
        </div>
      </section>

      <section className="flex items-center justify-center px-6 py-16">
        <div className="w-full max-w-sm animate-rise-in">
          <div className="mb-10 flex items-center gap-3 lg:hidden">
            <Logo size={32} />
            <span className="font-display text-lg font-medium tracking-tight">Voicollo</span>
          </div>
          <h2 className="font-display text-[28px] font-medium tracking-tight">Sign in</h2>
          <p className="mt-2 text-sm text-[var(--color-text-muted)]">Continue with the GitHub account that owns this console.</p>

          {error ? (
            <div className="mt-6">
              <ErrorBanner error={error} />
            </div>
          ) : null}

          <Button
            variant="primary"
            className="mt-8 h-11 w-full text-[15px]"
            onClick={start}
            loading={redirecting}
            icon={!redirecting && <GitHubMark />}
          >
            {redirecting ? 'Redirecting to GitHub…' : 'Continue with GitHub'}
            {!redirecting && <ArrowRight className="ml-auto size-4" />}
          </Button>

          <div className="mt-6 flex gap-3 rounded-[var(--radius-md)] border border-[var(--color-border-subtle)] bg-[var(--color-bg-raised)] p-4">
            <Lock className="mt-0.5 size-4 shrink-0 text-[var(--color-text-faint)]" />
            <p className="text-xs leading-relaxed text-[var(--color-text-faint)]">
              Restricted access. Only the configured GitHub user can sign in; every other account is rejected by the
              server.
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}

function GitHubMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" />
    </svg>
  )
}
