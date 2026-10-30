// Mirrors backend/app/schemas/*. Timestamps are ISO-8601 UTC strings ("…Z").

export type LogLevel = 'DEBUG' | 'INFO' | 'WARN' | 'ERROR' | 'FATAL'
export type Outcome = 'SUCCESS' | 'FAILURE' | 'PARTIAL'
export type ActorType = 'USER' | 'SERVICE' | 'SYSTEM'
export type LogType = 'app' | 'audit' | 'both'

export interface AppLogEntry {
  log_type: 'app'
  id: number
  source_service: string
  level: LogLevel
  message: string
  environment: string
  context_json: Record<string, unknown> | null
  trace_id: string | null
  created_at: string
  ingested_at: string
  timestamp: string
}

export interface AuditLogEntry {
  log_type: 'audit'
  id: number
  source_service: string
  environment: string | null
  actor_id: string
  actor_type: ActorType
  action: string
  target_resource: string
  outcome: Outcome
  ip_address: string | null
  detail_json: Record<string, unknown> | null
  event_time: string
  ingested_at: string
  timestamp: string
}

export type LogEntry = AppLogEntry | AuditLogEntry

export interface Paginated<T> {
  data: T[]
  total: number
  page: number
  page_size: number
  has_next: boolean
}

export interface LogQuery {
  log_type?: LogType
  level?: LogLevel[]
  outcome?: Outcome[]
  source_service?: string[]
  environment?: string
  start_time?: string
  end_time?: string
  trace_id?: string
  actor_id?: string
  action?: string
  q?: string
  sort?: 'asc' | 'desc'
  page?: number
  page_size?: number
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  username: string
  expires_in: number
}

export interface ServiceActivity {
  last_seen_at: string | null
  app_logs_24h: number
  errors_24h: number
  audit_logs_24h: number
}

export interface Service {
  id: string
  name: string
  description: string | null
  is_active: boolean
  is_protected: boolean
  created_at: string
  updated_at: string
  activity: ServiceActivity | null
}

export interface TimeBucket {
  start: string
  debug: number
  info: number
  warn: number
  error: number
  fatal: number
  audit: number
}

export interface Overview {
  window_hours: number
  bucket_seconds: number
  generated_at: string
  totals: {
    app_logs: number
    audit_logs: number
    errors: number
    active_services: number
    app_logs_all_time: number
    audit_logs_all_time: number
  }
  levels: Record<LogLevel, number>
  outcomes: Record<Outcome, number>
  error_rate: number
  timeline: TimeBucket[]
  top_services: { source_service: string; app_logs: number; errors: number; audit_logs: number }[]
  recent_errors: AppLogEntry[]
}

export interface DependencyStatus {
  status: 'ok' | 'error'
  latency_ms: number | null
  detail: string | null
}

export interface Health {
  status: 'healthy' | 'degraded'
  version: string
  uptime_seconds: number
  database: DependencyStatus
  cache: DependencyStatus
}

export interface VersionInfo {
  version: string
  git_sha: string
  build_date: string
  environment: string
}

export interface RetentionRun {
  status: 'SUCCESS' | 'FAILURE'
  started_at: string
  duration_seconds: number
  deleted_app_logs: number
  deleted_audit_logs: number
  trigger: 'schedule' | 'manual'
  error: string | null
}

export interface SystemStatus {
  health: Health
  version: VersionInfo
  metrics: {
    ingestion_total: number
    query_total: number
    cache_hits: number
    cache_misses: number
    cache_hit_ratio: number
    error_total: Record<string, number>
    since: string | null
  }
  retention: {
    policy: {
      enabled: boolean
      app_log_retention_days: number
      audit_log_retention_days: number
      schedule: string
      timezone: string
      next_run_at: string | null
    }
    last_run: RetentionRun | null
    running: boolean
  }
  rate_limit_per_minute: number
  signature_tolerance_seconds: number
}
