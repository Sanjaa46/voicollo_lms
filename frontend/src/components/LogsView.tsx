import React, { useState } from 'react';
import { Badge } from './Common';
import type { LogEntry } from '../services/api';

interface LogFiltersProps {
  onFilterChange: (filters: LogFilterValues) => void;
}

export interface LogFilterValues {
  log_type: 'app' | 'audit' | 'both';
  level?: string;
  source_service?: string;
  trace_id?: string;
  actor_id?: string;
}

export const LogFilters: React.FC<LogFiltersProps> = ({ onFilterChange }) => {
  const [logType, setLogType] = useState<'app' | 'audit' | 'both'>('both');
  const [level, setLevel] = useState<string>('');
  const [sourceService, setSourceService] = useState('');
  const [traceId, setTraceId] = useState('');
  const [actorId, setActorId] = useState('');

  const handleApplyFilters = () => {
    const filters: LogFilterValues = { log_type: logType };
    if (level) filters.level = level;
    if (sourceService) filters.source_service = sourceService;
    if (traceId) filters.trace_id = traceId;
    if (actorId) filters.actor_id = actorId;
    onFilterChange(filters);
  };

  const handleReset = () => {
    setLogType('both');
    setLevel('');
    setSourceService('');
    setTraceId('');
    setActorId('');
    onFilterChange({ log_type: 'both' });
  };

  const inputStyle = {
    width: '100%',
    padding: '8px 12px',
    border: '1px solid #e2e8f0',
    borderRadius: '8px',
    fontSize: '0.875rem',
    color: '#1e293b',
    background: '#fff',
    outline: 'none',
  };

  const labelStyle = {
    display: 'block',
    fontSize: '0.75rem',
    fontWeight: 600,
    color: '#64748b',
    marginBottom: '6px',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
  };

  return (
    <div className="rounded-xl mb-5" style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
      <div className="px-5 py-4" style={{ borderBottom: '1px solid #f1f5f9' }}>
        <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#475569' }}>Filter logs</span>
      </div>
      <div className="p-5">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div>
            <label style={labelStyle}>Log Type</label>
            <select value={logType} onChange={(e) => setLogType(e.target.value as 'app' | 'audit' | 'both')} style={inputStyle}>
              <option value="both">App & Audit</option>
              <option value="app">Application only</option>
              <option value="audit">Audit only</option>
            </select>
          </div>

          <div>
            <label style={labelStyle}>Severity</label>
            <select value={level} onChange={(e) => setLevel(e.target.value)} style={inputStyle}>
              <option value="">All levels</option>
              <option value="DEBUG">DEBUG</option>
              <option value="INFO">INFO</option>
              <option value="WARN">WARN</option>
              <option value="ERROR">ERROR</option>
              <option value="FATAL">FATAL</option>
            </select>
          </div>

          <div>
            <label style={labelStyle}>Source Service</label>
            <input type="text" value={sourceService} onChange={(e) => setSourceService(e.target.value)}
              placeholder="e.g., example-service" style={inputStyle}
              onFocus={e => { e.currentTarget.style.borderColor = '#3b82f6'; e.currentTarget.style.boxShadow = '0 0 0 3px rgba(59,130,246,0.1)'; }}
              onBlur={e => { e.currentTarget.style.borderColor = '#e2e8f0'; e.currentTarget.style.boxShadow = 'none'; }}
            />
          </div>

          <div>
            <label style={labelStyle}>Trace ID</label>
            <input type="text" value={traceId} onChange={(e) => setTraceId(e.target.value)}
              placeholder="Trace ID" style={{ ...inputStyle, fontFamily: 'monospace' }}
              onFocus={e => { e.currentTarget.style.borderColor = '#3b82f6'; e.currentTarget.style.boxShadow = '0 0 0 3px rgba(59,130,246,0.1)'; }}
              onBlur={e => { e.currentTarget.style.borderColor = '#e2e8f0'; e.currentTarget.style.boxShadow = 'none'; }}
            />
          </div>

          <div>
            <label style={labelStyle}>Actor ID</label>
            <input type="text" value={actorId} onChange={(e) => setActorId(e.target.value)}
              placeholder="Actor ID" style={inputStyle}
              onFocus={e => { e.currentTarget.style.borderColor = '#3b82f6'; e.currentTarget.style.boxShadow = '0 0 0 3px rgba(59,130,246,0.1)'; }}
              onBlur={e => { e.currentTarget.style.borderColor = '#e2e8f0'; e.currentTarget.style.boxShadow = 'none'; }}
            />
          </div>
        </div>

        <div className="flex gap-2 mt-5">
          <button onClick={handleApplyFilters}
            className="px-5 py-2 rounded-lg text-sm font-semibold transition-all"
            style={{ background: '#3b82f6', color: '#fff', border: 'none' }}
            onMouseEnter={e => e.currentTarget.style.background = '#2563eb'}
            onMouseLeave={e => e.currentTarget.style.background = '#3b82f6'}>
            Apply filters
          </button>
          <button onClick={handleReset}
            className="px-5 py-2 rounded-lg text-sm font-medium transition-all"
            style={{ background: '#f8fafc', color: '#64748b', border: '1px solid #e2e8f0' }}
            onMouseEnter={e => e.currentTarget.style.background = '#f1f5f9'}
            onMouseLeave={e => e.currentTarget.style.background = '#f8fafc'}>
            Reset
          </button>
        </div>
      </div>
    </div>
  );
};

interface LogTableProps {
  logs: LogEntry[];
  onViewDetails: (log: LogEntry) => void;
}

export const LogTable: React.FC<LogTableProps> = ({ logs, onViewDetails }) => {
  const formatDate = (dateString: string) => {
    const d = new Date(dateString);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' ' +
      d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
  };

  if (logs.length === 0) {
    return (
      <div className="rounded-xl p-12 text-center" style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
        <div style={{ fontSize: '2rem', marginBottom: '12px' }}>📭</div>
        <p style={{ color: '#64748b', fontSize: '0.9rem' }}>No logs match your filters.</p>
        <p style={{ color: '#94a3b8', fontSize: '0.8rem', marginTop: '4px' }}>Try adjusting the filter criteria above.</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl overflow-hidden" style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
      <div className="overflow-x-auto">
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
              {['Type', 'ID', 'Service', 'Status', 'Message / Action', 'Time', ''].map((h) => (
                <th key={h} style={{
                  padding: '10px 16px',
                  textAlign: 'left',
                  fontSize: '0.7rem',
                  fontWeight: 600,
                  color: '#94a3b8',
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  whiteSpace: 'nowrap',
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {logs.map((log, i) => (
              <tr key={`${log.log_type}-${log.id}`}
                style={{ borderBottom: i < logs.length - 1 ? '1px solid #f1f5f9' : 'none' }}
                onMouseEnter={e => (e.currentTarget.style.background = '#fafbff')}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>

                <td style={{ padding: '12px 16px', whiteSpace: 'nowrap' }}>
                  <span style={{
                    display: 'inline-flex', alignItems: 'center', gap: '5px',
                    fontSize: '0.7rem', fontWeight: 600,
                    color: log.log_type === 'app' ? '#7c3aed' : '#0284c7',
                    background: log.log_type === 'app' ? '#faf5ff' : '#f0f9ff',
                    border: `1px solid ${log.log_type === 'app' ? '#e9d5ff' : '#bae6fd'}`,
                    padding: '2px 8px', borderRadius: '999px',
                  }}>
                    {log.log_type === 'app' ? 'APP' : 'AUDIT'}
                  </span>
                </td>

                <td style={{ padding: '12px 16px', fontFamily: 'monospace', fontSize: '0.8rem', color: '#94a3b8' }}>
                  #{log.id}
                </td>

                <td style={{ padding: '12px 16px', fontSize: '0.8rem', color: '#475569', whiteSpace: 'nowrap' }}>
                  {log.source_service}
                </td>

                <td style={{ padding: '12px 16px', whiteSpace: 'nowrap' }}>
                  {log.log_type === 'app' && log.level ? (
                    <Badge level={log.level}>{log.level}</Badge>
                  ) : log.log_type === 'audit' && log.outcome ? (
                    <Badge outcome={log.outcome}>{log.outcome}</Badge>
                  ) : (
                    <span style={{ color: '#cbd5e1' }}>—</span>
                  )}
                </td>

                <td style={{ padding: '12px 16px', maxWidth: '240px' }}>
                  <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '0.82rem', color: '#334155' }}>
                    {log.log_type === 'app'
                      ? (log.message?.substring(0, 60) || '—')
                      : (log.action?.substring(0, 60) || '—')}
                  </div>
                </td>

                <td style={{ padding: '12px 16px', whiteSpace: 'nowrap', fontFamily: 'monospace', fontSize: '0.75rem', color: '#94a3b8' }}>
                  {formatDate(log.log_type === 'app' ? (log.created_at || '') : (log.event_time || ''))}
                </td>

                <td style={{ padding: '12px 16px', whiteSpace: 'nowrap' }}>
                  <button onClick={() => onViewDetails(log)}
                    style={{ fontSize: '0.8rem', fontWeight: 600, color: '#3b82f6', background: 'none', border: 'none', cursor: 'pointer', padding: '4px 0' }}
                    onMouseEnter={e => e.currentTarget.style.color = '#1d4ed8'}
                    onMouseLeave={e => e.currentTarget.style.color = '#3b82f6'}>
                    View →
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};