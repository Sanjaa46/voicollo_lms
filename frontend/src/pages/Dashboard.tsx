import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { useAuth } from '../services/authContext';
import { logsAPI } from '../services/api';
import type { LogEntry } from '../services/api';
import { PageShell, LoadingSpinner, ErrorAlert, Pagination } from '../components/Common';
import { LogFilters, LogTable } from '../components/LogsView';

export const Dashboard: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<any>({ log_type: 'both', page_size: 50 });
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) navigate('/');
  }, [isAuthenticated, isLoading, navigate]);

  const {
    data,
    isLoading: logsLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ['logs', filters, page],
    queryFn: () => logsAPI.queryLogs({ ...filters, page }),
    enabled: isAuthenticated && !isLoading,
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });

  const logs = data?.data ?? [];
  const total = data?.total ?? 0;
  const hasNext = data?.has_next ?? false;

  const handleFilterChange = (newFilters: any) => {
    setFilters(newFilters);
    setPage(1);
  };

  const handleViewDetails = (log: LogEntry) => {
    navigate(`/logs/${log.log_type}/${log.id}`);
  };

  const handleExport = async (format: 'json' | 'csv') => {
    try {
      setExporting(true);
      setExportError(null);
      const blob = await logsAPI.exportLogs({ ...filters, format });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `logs-export-${new Date().toISOString().split('T')[0]}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error('Export failed:', err);
      setExportError('Failed to export logs. Please try again.');
    } finally {
      setExporting(false);
    }
  };

  if (isLoading) return <LoadingSpinner />;

  return (
    <PageShell>
      <main style={{ padding: '32px 32px', maxWidth: '1200px' }}>
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#0f172a', letterSpacing: '-0.02em', marginBottom: '4px' }}>
              Logs
            </h1>
            <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
              {total > 0 ? (
                <><span style={{ color: '#3b82f6', fontWeight: 600 }}>{total.toLocaleString()}</span> total entries</>
              ) : 'No entries found'}
            </p>
          </div>

          <div className="flex gap-2">
            <ExportButton onClick={() => handleExport('json')} disabled={exporting || logs.length === 0} label="JSON" />
            <ExportButton onClick={() => handleExport('csv')} disabled={exporting || logs.length === 0} label="CSV" />
          </div>
        </div>

        {isError && (
          <ErrorAlert message={(error as Error)?.message ?? 'Failed to load logs. Please try again.'} onDismiss={() => {}} />
        )}
        {exportError && <ErrorAlert message={exportError} onDismiss={() => setExportError(null)} />}

        <LogFilters onFilterChange={handleFilterChange} />

        {logsLoading ? (
          <div className="flex items-center justify-center py-20">
            <div className="relative w-10 h-10">
              <div className="absolute inset-0 rounded-full border-2 border-blue-100"></div>
              <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-blue-500 animate-spin"></div>
            </div>
          </div>
        ) : (
          <>
            <LogTable logs={logs} onViewDetails={handleViewDetails} />
            {logs.length > 0 && (
              <Pagination page={page} hasNext={hasNext}
                onPrevious={() => setPage(p => Math.max(1, p - 1))}
                onNext={() => setPage(p => p + 1)} />
            )}
          </>
        )}
      </main>
    </PageShell>
  );
};

const ExportButton: React.FC<{ onClick: () => void; disabled: boolean; label: string }> = ({ onClick, disabled, label }) => (
  <button onClick={onClick} disabled={disabled}
    className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all"
    style={{
      background: disabled ? '#f8fafc' : '#fff',
      color: disabled ? '#cbd5e1' : '#475569',
      border: '1px solid',
      borderColor: '#e2e8f0',
      cursor: disabled ? 'not-allowed' : 'pointer',
    }}
    onMouseEnter={e => { if (!disabled) { e.currentTarget.style.borderColor = '#3b82f6'; e.currentTarget.style.color = '#3b82f6'; } }}
    onMouseLeave={e => { if (!disabled) { e.currentTarget.style.borderColor = '#e2e8f0'; e.currentTarget.style.color = '#475569'; } }}>
    <DownloadIcon />
    Export {label}
  </button>
);

const DownloadIcon = () => (
  <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
    <path d="M6.5 1v7M3.5 5.5l3 3 3-3M1.5 10.5h10" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);