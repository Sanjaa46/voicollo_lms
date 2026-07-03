import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../services/authContext';
import { adminAPI } from '../services/api';
import { PageShell, LoadingSpinner, ErrorAlert } from '../components/Common';

export const Health: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) navigate('/');
  }, [isAuthenticated, isLoading, navigate]);

  const enabled = isAuthenticated && !isLoading;

  const {
    data: health,
    isError: healthError,
    refetch: refetchHealth,
    isFetching: healthFetching,
  } = useQuery({
    queryKey: ['health'],
    queryFn: () => adminAPI.health(),
    enabled,
    refetchInterval: 15_000, // health should be near-real-time
  });

  const {
    data: metrics,
    isError: metricsError,
    refetch: refetchMetrics,
    isFetching: metricsFetching,
  } = useQuery({
    queryKey: ['metrics'],
    queryFn: () => adminAPI.metrics(),
    enabled,
    refetchInterval: 60_000, // metrics can lag a bit, less churn
  });

  const isHealthy = (status: string) => status === 'healthy' || status === 'ok';
  const refreshing = healthFetching || metricsFetching;
  const error = healthError || metricsError;

  const handleRefresh = () => {
    refetchHealth();
    refetchMetrics();
  };

  if (isLoading || (!health && !metrics && refreshing)) {
    return <LoadingSpinner message="Loading health and metrics..." />;
  }

  return (
    <PageShell>
      <main style={{ padding: '32px', maxWidth: '1200px' }}>
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#0f172a', letterSpacing: '-0.02em', marginBottom: '4px' }}>
              Health & Metrics
            </h1>
            <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>System status and performance overview</p>
          </div>
          <button onClick={handleRefresh} disabled={refreshing}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all"
            style={{
              background: '#fff',
              color: refreshing ? '#94a3b8' : '#475569',
              border: '1px solid #e2e8f0',
              cursor: refreshing ? 'not-allowed' : 'pointer',
            }}
            onMouseEnter={e => { if (!refreshing) { e.currentTarget.style.borderColor = '#3b82f6'; e.currentTarget.style.color = '#3b82f6'; } }}
            onMouseLeave={e => { if (!refreshing) { e.currentTarget.style.borderColor = '#e2e8f0'; e.currentTarget.style.color = '#475569'; } }}>
            <RefreshIcon spinning={refreshing} />
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>

        {error && <ErrorAlert message="Failed to load health and metrics data." onDismiss={() => {}} />}

        {health && (
          <section className="mb-8">
            <SectionLabel>System Health</SectionLabel>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <HealthCard
                title="Overall"
                status={health.status}
                healthy={isHealthy(health.status)}
                meta={[
                  { label: 'Version', value: health.version },
                  { label: 'Uptime', value: `${Math.floor(health.uptime_seconds / 3600)}h ${Math.floor((health.uptime_seconds % 3600) / 60)}m` },
                ]}
              />
              <HealthCard
                title="Database"
                status={health.database.status}
                healthy={isHealthy(health.database.status)}
                meta={[
                  health.database.latency_ms !== undefined
                    ? { label: 'Latency', value: `${health.database.latency_ms.toFixed(2)}ms`, mono: true }
                    : null,
                  health.database.detail ? { label: 'Detail', value: health.database.detail } : null,
                ].filter(Boolean) as any}
              />
              <HealthCard
                title="Cache (Redis)"
                status={health.cache.status}
                healthy={isHealthy(health.cache.status)}
                meta={[
                  health.cache.latency_ms !== undefined
                    ? { label: 'Latency', value: `${health.cache.latency_ms.toFixed(2)}ms`, mono: true }
                    : null,
                  health.cache.detail ? { label: 'Detail', value: health.cache.detail } : null,
                ].filter(Boolean) as any}
              />
            </div>
          </section>
        )}

        {metrics && (
          <section>
            <SectionLabel>Metrics</SectionLabel>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-3 gap-4 mb-4">
              <MetricCard label="Ingested Logs" value={metrics.ingestion_total.toLocaleString()} />
              <MetricCard label="Total Queries" value={metrics.query_total.toLocaleString()} />
              <MetricCard label="Cache Hits" value={metrics.cache_hits.toLocaleString()} accent="#10b981" />
              <MetricCard label="Cache Misses" value={metrics.cache_misses.toLocaleString()} accent="#f59e0b" />
              {metrics.retention_last_run && (
                <MetricCard
                  label="Retention Deleted"
                  value={(metrics.retention_deleted_count || 0).toLocaleString()}
                  sub={new Date(metrics.retention_last_run).toLocaleDateString()}
                />
              )}

              <div className="col-span-2 md:col-span-1 rounded-xl p-5" style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
                <div style={{ fontSize: '0.7rem', fontWeight: 600, color: '#94a3b8', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '8px' }}>
                  Cache Hit Ratio
                </div>
                <div style={{ fontSize: '2rem', fontWeight: 700, color: '#10b981', letterSpacing: '-0.03em', marginBottom: '12px' }}>
                  {(metrics.cache_hit_ratio * 100).toFixed(1)}%
                </div>
                <div style={{ height: '6px', background: '#f1f5f9', borderRadius: '999px', overflow: 'hidden' }}>
                  <div style={{
                    height: '100%',
                    width: `${metrics.cache_hit_ratio * 100}%`,
                    background: 'linear-gradient(90deg, #10b981, #34d399)',
                    borderRadius: '999px',
                    transition: 'width 0.6s ease',
                  }} />
                </div>
              </div>
            </div>

            {metrics.error_total && Object.keys(metrics.error_total).length > 0 && (
              <div className="rounded-xl p-5" style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
                <div style={{ fontSize: '0.7rem', fontWeight: 600, color: '#94a3b8', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '16px' }}>
                  Error Distribution
                </div>
                <div className="space-y-2">
                  {Object.entries(metrics.error_total).map(([code, count]) => (
                    <div key={code} className="flex items-center justify-between py-1.5"
                      style={{ borderBottom: '1px solid #f8fafc' }}>
                      <span style={{ fontFamily: 'monospace', fontSize: '0.82rem', color: '#475569' }}>{code}</span>
                      <span style={{ fontWeight: 700, color: '#ef4444', fontSize: '0.9rem' }}>{count as any}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>
        )}
      </main>
    </PageShell>
  );
};

const SectionLabel: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div style={{ fontSize: '0.7rem', fontWeight: 600, color: '#94a3b8', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '12px' }}>
    {children}
  </div>
);

const HealthCard: React.FC<{
  title: string;
  status: string;
  healthy: boolean;
  meta: Array<{ label: string; value: string; mono?: boolean }>;
}> = ({ title, status, healthy, meta }) => (
  <div className="rounded-xl p-5" style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
    <div className="flex items-center justify-between mb-4">
      <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#334155' }}>{title}</span>
      <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full"
        style={{
          background: healthy ? '#f0fdf4' : '#fff1f2',
          color: healthy ? '#166534' : '#be123c',
          fontSize: '0.7rem', fontWeight: 600,
        }}>
        <span className="w-1.5 h-1.5 rounded-full" style={{ background: healthy ? '#10b981' : '#ef4444' }}></span>
        {status.toUpperCase()}
      </span>
    </div>
    <div className="space-y-2">
      {meta.map(({ label, value, mono }) => (
        <div key={label} className="flex items-center justify-between">
          <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>{label}</span>
          <span style={{ fontSize: '0.8rem', color: '#475569', fontFamily: mono ? 'monospace' : 'inherit', fontWeight: 500 }}>
            {value}
          </span>
        </div>
      ))}
    </div>
  </div>
);

const MetricCard: React.FC<{ label: string; value: string; accent?: string; sub?: string }> = ({
  label, value, accent = '#3b82f6', sub,
}) => (
  <div className="rounded-xl p-5" style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
    <div style={{ fontSize: '0.7rem', fontWeight: 600, color: '#94a3b8', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '8px' }}>
      {label}
    </div>
    <div style={{ fontSize: '2rem', fontWeight: 700, color: accent, letterSpacing: '-0.03em' }}>
      {value}
    </div>
    {sub && <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '4px' }}>{sub}</div>}
  </div>
);

const RefreshIcon: React.FC<{ spinning: boolean }> = ({ spinning }) => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none"
    style={{ animation: spinning ? 'spin 1s linear infinite' : 'none' }}>
    <path d="M12 7A5 5 0 0 1 2.5 10M2 7A5 5 0 0 1 11.5 4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    <path d="M11 1v3h-3M3 13v-3h3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);