import React, { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../services/authContext';
import { logsAPI } from '../services/api';
import { PageShell, LoadingSpinner, ErrorAlert, Badge } from '../components/Common';

export const LogDetails: React.FC = () => {
  const { logType, logId } = useParams<{ logType: 'app' | 'audit'; logId: string }>();
  const navigate = useNavigate();
  const { isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) navigate('/');
  }, [isAuthenticated, isLoading, navigate]);

  const numericId = logId ? parseInt(logId, 10) : NaN;
  const validParams = !!logType && Number.isFinite(numericId);

  const {
    data: log,
    isLoading: logLoading,
    isError,
  } = useQuery({
    queryKey: ['log', logType, numericId],
    queryFn: () => logsAPI.getLog(logType as 'app' | 'audit', numericId),
    enabled: isAuthenticated && !isLoading && validParams,
  });

  const formatDate = (dateString: string) => new Date(dateString).toLocaleString();

  if (isLoading || (logLoading && validParams)) return <LoadingSpinner message="Loading log details..." />;

  return (
    <PageShell>
      <main style={{ padding: '32px', maxWidth: '900px' }}>
        <button onClick={() => navigate('/dashboard')}
          className="flex items-center gap-1.5 mb-6 text-sm font-medium transition-colors"
          style={{ color: '#64748b', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
          onMouseEnter={e => e.currentTarget.style.color = '#3b82f6'}
          onMouseLeave={e => e.currentTarget.style.color = '#64748b'}>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M9 2L4 7l5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Back to Logs
        </button>

        {!validParams && (
          <ErrorAlert message="Invalid log reference in URL." onDismiss={() => {}} />
        )}
        {validParams && isError && (
          <ErrorAlert message="Failed to load log details. Log may not exist." onDismiss={() => {}} />
        )}

        {log && (
          <div className="rounded-xl overflow-hidden" style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
            <div style={{ height: '4px', background: log.log_type === 'app' ? 'linear-gradient(90deg,#7c3aed,#a78bfa)' : 'linear-gradient(90deg,#0284c7,#38bdf8)' }} />

            <div className="flex items-start justify-between gap-4 px-8 py-6"
              style={{ borderBottom: '1px solid #f1f5f9' }}>
              <div>
                <div className="flex items-center gap-3 mb-1">
                  <span style={{
                    fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
                    color: log.log_type === 'app' ? '#7c3aed' : '#0284c7',
                    background: log.log_type === 'app' ? '#faf5ff' : '#f0f9ff',
                    border: `1px solid ${log.log_type === 'app' ? '#e9d5ff' : '#bae6fd'}`,
                    padding: '2px 8px', borderRadius: '999px',
                  }}>
                    {log.log_type === 'app' ? 'App Log' : 'Audit Log'}
                  </span>
                  <span style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: '#94a3b8' }}>#{log.id}</span>
                </div>
                <h1 style={{ fontSize: '1.4rem', fontWeight: 700, color: '#0f172a', letterSpacing: '-0.02em' }}>
                  {log.log_type === 'app' ? 'Application Log' : 'Audit Log'} Details
                </h1>
                <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '4px' }}>
                  Ingested {formatDate(log.ingested_at)}
                </p>
              </div>
              {log.log_type === 'app' && log.level && <Badge level={log.level}>{log.level}</Badge>}
              {log.log_type === 'audit' && log.outcome && <Badge outcome={log.outcome}>{log.outcome}</Badge>}
            </div>

            <div className="px-8 py-6 space-y-8">
              <FieldSection title="Common Information">
                <FieldGrid>
                  <Field label="Source Service" value={log.source_service} />
                  <Field label="Environment" value={log.environment} />
                </FieldGrid>
              </FieldSection>

              {log.log_type === 'app' && (
                <FieldSection title="Application Log Details">
                  <FieldGrid>
                    <Field label="Level" value={<Badge level={log.level}>{log.level}</Badge>} />
                    <Field label="Created At" value={log.created_at ? formatDate(log.created_at) : 'N/A'} />
                    {log.trace_id && (
                      <div className="md:col-span-2">
                        <Field label="Trace ID" value={log.trace_id} mono />
                      </div>
                    )}
                  </FieldGrid>

                  <div className="mt-6">
                    <FieldLabel>Message</FieldLabel>
                    <div className="mt-2 rounded-lg p-4" style={{ background: '#f8fafc', border: '1px solid #e2e8f0' }}>
                      <p style={{ color: '#1e293b', fontSize: '0.875rem', lineHeight: 1.7, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                        {log.message}
                      </p>
                    </div>
                  </div>

                  {log.context_json && Object.keys(log.context_json).length > 0 && (
                    <div className="mt-4">
                      <FieldLabel>Context</FieldLabel>
                      <CodeBlock>{JSON.stringify(log.context_json, null, 2)}</CodeBlock>
                    </div>
                  )}
                </FieldSection>
              )}

              {log.log_type === 'audit' && (
                <FieldSection title="Audit Log Details">
                  <FieldGrid>
                    <Field label="Actor ID" value={log.actor_id} />
                    <Field label="Actor Type" value={<Badge>{log.actor_type}</Badge>} />
                    <Field label="Action" value={log.action} />
                    <Field label="Outcome" value={<Badge outcome={log.outcome}>{log.outcome}</Badge>} />
                    <div className="md:col-span-2">
                      <Field label="Target Resource" value={log.target_resource} mono />
                    </div>
                    {log.ip_address && <Field label="IP Address" value={log.ip_address} mono />}
                    <Field label="Event Time" value={log.event_time ? formatDate(log.event_time) : 'N/A'} />
                  </FieldGrid>

                  {log.detail_json && Object.keys(log.detail_json).length > 0 && (
                    <div className="mt-4">
                      <FieldLabel>Details</FieldLabel>
                      <CodeBlock>{JSON.stringify(log.detail_json, null, 2)}</CodeBlock>
                    </div>
                  )}
                </FieldSection>
              )}

              <FieldSection title="Raw Data">
                <CodeBlock>{JSON.stringify(log, null, 2)}</CodeBlock>
              </FieldSection>
            </div>
          </div>
        )}
      </main>
    </PageShell>
  );
};

const FieldSection: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div>
    <div style={{ fontSize: '0.7rem', fontWeight: 600, color: '#94a3b8', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '14px' }}>
      {title}
    </div>
    {children}
  </div>
);

const FieldGrid: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{children}</div>
);

const FieldLabel: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div style={{ fontSize: '0.72rem', fontWeight: 600, color: '#94a3b8', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '4px' }}>
    {children}
  </div>
);

const Field: React.FC<{ label: string; value: React.ReactNode; mono?: boolean }> = ({ label, value, mono }) => (
  <div>
    <FieldLabel>{label}</FieldLabel>
    <div style={{
      fontSize: '0.875rem',
      color: '#334155',
      fontFamily: mono ? 'monospace' : 'inherit',
      wordBreak: 'break-all',
    }}>
      {value ?? <span style={{ color: '#cbd5e1' }}>—</span>}
    </div>
  </div>
);

const CodeBlock: React.FC<{ children: string }> = ({ children }) => (
  <div className="rounded-lg overflow-x-auto" style={{ background: '#0f172a', border: '1px solid #1e293b' }}>
    <pre style={{ padding: '16px', color: '#94a3b8', fontSize: '0.775rem', lineHeight: 1.7, margin: 0, fontFamily: 'monospace' }}>
      {children}
    </pre>
  </div>
);