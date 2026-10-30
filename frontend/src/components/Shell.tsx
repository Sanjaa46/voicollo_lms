import { useState, type ReactNode } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Activity, Boxes, LayoutDashboard, LogOut, Menu, Moon, ScrollText, Sun, X } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { timezoneLabel, timezoneName } from '../lib/format'
import { useTheme } from '../lib/theme'
import { IconButton, StatusDot } from './ui'
import { cn } from '../lib/cn'

const NAV = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/logs', label: 'Logs', icon: ScrollText },
  { to: '/services', label: 'Services', icon: Boxes },
  { to: '/system', label: 'System', icon: Activity },
]

export function Logo({ size = 28 }: { size?: number }) {
  return (
    <div
      className="flex items-center justify-center rounded-[var(--radius-sm)] bg-[var(--color-amber)]"
      style={{ width: size, height: size }}
      aria-hidden
    >
      <svg width={size * 0.56} height={size * 0.56} viewBox="0 0 16 16" fill="none">
        <rect x="1" y="2.5" width="14" height="2" rx="1" fill="#140b02" />
        <rect x="1" y="7" width="9" height="2" rx="1" fill="#140b02" opacity=".75" />
        <rect x="1" y="11.5" width="11.5" height="2" rx="1" fill="#140b02" opacity=".5" />
      </svg>
    </div>
  )
}

function versionLabel(version?: string, env?: string): string {
  if (!version) return ''
  if (!env || env === 'production') return `v${version}`
  return `v${version} · ${env === 'development' ? 'dev' : env}`
}

function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { session, signOut } = useAuth()
  const version = useQuery({ queryKey: ['version'], queryFn: api.version, staleTime: Infinity })
  const health = useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 30_000, retry: false })
  const healthy = health.data?.status === 'healthy'

  return (
    <>
      {open && <div aria-hidden onClick={onClose} className="fixed inset-0 z-40 bg-black/50 lg:hidden" />}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex w-[248px] -translate-x-full flex-col border-r border-[var(--color-border-subtle)] bg-[var(--color-bg-raised)] transition-transform duration-200 ease-out',
          'lg:sticky lg:top-0 lg:h-screen lg:w-[220px] lg:translate-x-0',
          open && 'translate-x-0',
        )}
      >
        <div className="flex h-16 items-center justify-between px-5">
          <div className="flex items-center gap-2.5">
            <Logo />
            <div className="leading-none">
              <div className="font-display text-[15px] font-medium tracking-tight">Voicollo</div>
              <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--color-text-faint)]">
                log console
              </div>
            </div>
          </div>
          <IconButton label="Close menu" onClick={onClose} className="lg:hidden">
            <X className="size-4" />
          </IconButton>
        </div>

        <nav className="flex-1 space-y-0.5 px-3 py-2">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={onClose}
              className={({ isActive }) =>
                cn(
                  'group relative flex h-9 items-center gap-3 rounded-[var(--radius-sm)] px-3 text-sm transition-colors',
                  isActive
                    ? 'bg-[var(--color-bg-panel)] text-[var(--color-text)]'
                    : 'text-[var(--color-text-muted)] hover:bg-[var(--color-bg-panel)] hover:text-[var(--color-text)]',
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span className="absolute inset-y-2 left-0 w-[3px] rounded-r bg-[var(--color-amber)]" aria-hidden />
                  )}
                  <Icon className={cn('size-4', isActive && 'text-[var(--color-accent-text)]')} />
                  {label}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="space-y-3 border-t border-[var(--color-border-subtle)] p-4">
          <div className="flex items-center justify-between gap-2 font-mono text-[11px] text-[var(--color-text-faint)]">
            <span className="shrink-0">
              <StatusDot ok={healthy} live label={health.isLoading ? 'checking' : healthy ? 'online' : 'degraded'} />
            </span>
            <span className="truncate" title={version.data?.git_sha}>
              {versionLabel(version.data?.version, version.data?.environment)}
            </span>
          </div>
          <div className="flex items-center justify-between gap-2 rounded-[var(--radius-sm)] border border-[var(--color-border-subtle)] bg-[var(--color-bg)] px-2.5 py-2">
            <div className="flex min-w-0 items-center gap-2">
              <img
                src={`https://github.com/${session?.username}.png?size=48`}
                alt=""
                className="size-6 rounded-full bg-[var(--color-bg-panel)]"
                onError={(e) => (e.currentTarget.style.visibility = 'hidden')}
              />
              <span className="truncate text-xs font-medium">{session?.username}</span>
            </div>
            <IconButton label="Sign out" onClick={() => void signOut()}>
              <LogOut className="size-3.5" />
            </IconButton>
          </div>
        </div>
      </aside>
    </>
  )
}

function TopBar({ onMenu, children }: { onMenu: () => void; children?: ReactNode }) {
  const [theme, toggle] = useTheme()
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-[var(--color-border-subtle)] bg-[color-mix(in_srgb,var(--color-bg)_85%,transparent)] px-4 backdrop-blur-md sm:px-6">
      <IconButton label="Open menu" onClick={onMenu} className="lg:hidden">
        <Menu className="size-4" />
      </IconButton>
      <div className="flex-1">{children}</div>
      <span
        title={`Times are shown in ${timezoneName}`}
        className="hidden rounded-full border border-[var(--color-border)] px-2.5 py-1 font-mono text-[11px] text-[var(--color-text-faint)] sm:inline"
      >
        {timezoneLabel}
      </span>
      <IconButton label={theme === 'dark' ? 'Light theme' : 'Dark theme'} onClick={toggle}>
        {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
      </IconButton>
    </header>
  )
}

export function Shell() {
  const [open, setOpen] = useState(false)

  return (
    <div className="flex min-h-screen">
      <Sidebar open={open} onClose={() => setOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar onMenu={() => setOpen(true)} />
        <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 sm:px-6 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
