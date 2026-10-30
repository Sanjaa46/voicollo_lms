import { readSession, writeSession, type Session } from './session'
import type {
  LogEntry,
  LogQuery,
  Overview,
  Paginated,
  RetentionRun,
  Service,
  SystemStatus,
  TokenResponse,
  VersionInfo,
  Health,
} from './types'

// Same origin in production (FastAPI serves the SPA); Vite proxies /api in dev.
const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api/v1'
const REFRESH_MARGIN_MS = 30_000

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly requestId?: string
  readonly details?: Record<string, unknown> | null

  constructor(status: number, code: string, message: string, requestId?: string, details?: Record<string, unknown> | null) {
    super(message)
    this.status = status
    this.code = code
    this.requestId = requestId
    this.details = details
  }

  get fieldErrors(): Record<string, string[]> {
    return ((this.details?.field_errors as Record<string, string[]>) ?? {}) as Record<string, string[]>
  }
}

type Query = Record<string, string | number | boolean | string[] | undefined | null>

function buildUrl(path: string, query?: Query): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value === undefined || value === null || value === '') continue
    if (Array.isArray(value)) value.forEach((v) => params.append(key, v))
    else params.set(key, String(value))
  }
  const qs = params.toString()
  return `${BASE}${path}${qs ? `?${qs}` : ''}`
}

async function toError(response: Response): Promise<ApiError> {
  try {
    const body = await response.json()
    return new ApiError(
      response.status,
      body.error_code ?? 'HTTP_ERROR',
      body.message ?? response.statusText,
      body.request_id,
      body.details,
    )
  } catch {
    return new ApiError(response.status, 'HTTP_ERROR', response.statusText || 'Request failed')
  }
}

export function toSession(tokens: TokenResponse): Session {
  return {
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    username: tokens.username,
    expiresAt: Date.now() + tokens.expires_in * 1000,
  }
}

// ---------------------------------------------------------------- refresh
// Single flight: concurrent 401s share one refresh. The refresh call uses
// plain fetch (never `request`), so a failing refresh cannot recurse/deadlock.
let refreshing: Promise<Session | null> | null = null

export function refreshSession(): Promise<Session | null> {
  refreshing ??= (async () => {
    const current = readSession()
    if (!current?.refreshToken) return null
    try {
      const response = await fetch(buildUrl('/auth/refresh'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: current.refreshToken }),
      })
      if (response.status >= 500) return current // server trouble is not a sign-out
      if (!response.ok) {
        // Another tab may have rotated the token a moment ago; use theirs.
        const latest = readSession()
        if (latest && latest.refreshToken !== current.refreshToken) return latest
        writeSession(null)
        return null
      }
      const session = toSession((await response.json()) as TokenResponse)
      writeSession(session)
      return session
    } catch {
      return current // network blip: keep the session, let the caller fail
    }
  })().finally(() => {
    refreshing = null
  })
  return refreshing
}

async function validAccessToken(): Promise<string | null> {
  let session = readSession()
  if (session && session.expiresAt - Date.now() < REFRESH_MARGIN_MS) {
    session = await refreshSession()
  }
  return session?.accessToken ?? null
}

// ---------------------------------------------------------------- request
interface RequestOptions {
  method?: string
  query?: Query
  body?: unknown
  auth?: boolean
  signal?: AbortSignal
}

async function send(path: string, opts: RequestOptions, token: string | null): Promise<Response> {
  const headers: Record<string, string> = {}
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`
  return fetch(buildUrl(path, opts.query), {
    method: opts.method ?? 'GET',
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    signal: opts.signal,
  })
}

export async function requestRaw(path: string, opts: RequestOptions = {}): Promise<Response> {
  const auth = opts.auth ?? true
  let response = await send(path, opts, auth ? await validAccessToken() : null)
  if (auth && response.status === 401) {
    const session = await refreshSession()
    if (session) response = await send(path, opts, session.accessToken)
  }
  if (!response.ok) throw await toError(response)
  return response
}

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const response = await requestRaw(path, opts)
  return (response.status === 204 ? undefined : await response.json()) as T
}

// ---------------------------------------------------------------- endpoints
export const api = {
  loginUrl: () => request<{ authorization_url: string }>('/auth/login', { auth: false }),
  callback: (code: string, state: string) =>
    request<TokenResponse>('/auth/callback', { method: 'POST', body: { code, state }, auth: false }),
  logout: () => request<void>('/auth/logout', { method: 'POST' }),
  me: () => request<{ username: string }>('/auth/me'),

  logs: (query: LogQuery, signal?: AbortSignal) =>
    request<Paginated<LogEntry>>('/logs', { query: query as unknown as Query, signal }),
  log: (type: 'app' | 'audit', id: number) => request<LogEntry>(`/logs/${type}/${id}`),
  exportLogs: (query: LogQuery & { format: 'json' | 'csv'; limit?: number }) =>
    requestRaw('/logs/export', { query: query as unknown as Query }),

  overview: (hours: number) => request<Overview>('/stats/overview', { query: { hours } }),

  services: (params: { q?: string; status?: 'active' | 'disabled' } = {}) =>
    request<{ data: Service[]; total: number }>('/services', { query: params }),
  createService: (body: { id: string; name: string; description?: string }) =>
    request<Service>('/services', { method: 'POST', body }),
  updateService: (id: string, body: { name?: string; description?: string | null }) =>
    request<Service>(`/services/${encodeURIComponent(id)}`, { method: 'PATCH', body }),
  setServiceActive: (id: string, active: boolean) =>
    request<Service>(`/services/${encodeURIComponent(id)}/${active ? 'enable' : 'disable'}`, {
      method: 'POST',
    }),

  systemStatus: () => request<SystemStatus>('/system/status'),
  runRetention: () => request<RetentionRun>('/retention/run', { method: 'POST' }),
  health: () => request<Health>('/health', { auth: false }),
  version: () => request<VersionInfo>('/version', { auth: false }),
}
