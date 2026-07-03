import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../services/authContext';
import { servicesAPI } from '../services/api';
import type { ServiceEntry, DisableServiceResponse, EnableServiceResponse } from '../services/api';
import { PageShell, LoadingSpinner, ErrorAlert, SuccessAlert } from '../components/Common';

// ─── Page ────────────────────────────────────────────────────────────────────

export const Services: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [success, setSuccess] = useState<string | null>(null);
  const [toggleError, setToggleError] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  // Filter input state (live typing, not yet applied)
  const [filterName, setFilterName] = useState('');
  const [filterId, setFilterId] = useState('');
  // Applied filter state — only changes on "Apply filters" / "Reset", drives the query key
  const [appliedFilters, setAppliedFilters] = useState<{ name?: string; id?: string }>({});

  const [showRegister, setShowRegister] = useState(false);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) navigate('/');
  }, [isAuthenticated, isLoading, navigate]);

  const enabled = isAuthenticated && !isLoading;

  const {
    data: services = [],
    isLoading: servicesLoading,
    isError: servicesQueryError,
  } = useQuery({
    queryKey: ['services', appliedFilters],
    queryFn: async () => {
      const data = await servicesAPI.queryServices({ name: appliedFilters.name, id: appliedFilters.id });
      return Array.isArray(data)
        ? data
        : Array.isArray((data as any)?.services)
          ? (data as any).services
          : Array.isArray((data as any)?.data)
            ? (data as any).data
            : [];
    },
    enabled,
  });

  const toggleMutation = useMutation<
    DisableServiceResponse | EnableServiceResponse,
    Error,
    ServiceEntry
  >({
    mutationFn: (service) =>
      service.is_active ? servicesAPI.disableService(service.id) : servicesAPI.enableService(service.id),
  });

  const handleToggle = (service: ServiceEntry) => {
    setToggleError(null);
    setSuccess(null);
    setTogglingId(service.id);
    toggleMutation.mutate(service, {
      onSuccess: () => {
        setSuccess(`Service "${service.name}" ${service.is_active ? 'disabled' : 'enabled'}.`);
        queryClient.invalidateQueries({ queryKey: ['services'] });
      },
      onError: (err) => {
        console.error('Toggle failed:', err);
        setToggleError(`Failed to ${service.is_active ? 'disable' : 'enable'} service. If you see a network error, ensure your backend allows PATCH requests in its CORS policy.`);
      },
      onSettled: () => setTogglingId(null),
    });
  };

  const handleFilterApply = () => setAppliedFilters({ name: filterName || undefined, id: filterId || undefined });
  const handleFilterReset = () => {
    setFilterName('');
    setFilterId('');
    setAppliedFilters({});
  };

  const handleRegistered = (name: string) => {
    setShowRegister(false);
    setSuccess(`Service "${name}" registered successfully.`);
    queryClient.invalidateQueries({ queryKey: ['services'] });
  };

  if (isLoading) return <LoadingSpinner />;

  const enabledCount = services.filter((s: ServiceEntry) => s.is_active).length;
  const disabledCount = services.length - enabledCount;

  const displayError = toggleError ?? (servicesQueryError ? 'Failed to load services. Please try again.' : null);

  return (
    <PageShell>
      <main style={{ padding: '32px', maxWidth: '1200px' }}>

        {/* Page header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#0f172a', letterSpacing: '-0.02em', marginBottom: '4px' }}>
              Services
            </h1>
            <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
              {services.length > 0 ? (
                <>
                  <span style={{ color: '#3b82f6', fontWeight: 600 }}>{services.length}</span> registered
                  {enabledCount > 0 && <> · <span style={{ color: '#10b981', fontWeight: 600 }}>{enabledCount}</span> active</>}
                  {disabledCount > 0 && <> · <span style={{ color: '#94a3b8', fontWeight: 600 }}>{disabledCount}</span> disabled</>}
                </>
              ) : 'No services registered'}
            </p>
          </div>
          <button
            onClick={() => setShowRegister(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all"
            style={{ background: '#3b82f6', color: '#fff', border: 'none', cursor: 'pointer' }}
            onMouseEnter={e => e.currentTarget.style.background = '#2563eb'}
            onMouseLeave={e => e.currentTarget.style.background = '#3b82f6'}>
            <PlusIcon />
            Register service
          </button>
        </div>

        {displayError && <ErrorAlert message={displayError} onDismiss={() => setToggleError(null)} />}
        {success && <SuccessAlert message={success} onDismiss={() => setSuccess(null)} />}

        {/* Filters */}
        <div className="rounded-xl mb-5" style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
          <div className="px-5 py-4" style={{ borderBottom: '1px solid #f1f5f9' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#475569' }}>Filter services</span>
          </div>
          <div className="p-5">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <FilterLabel>Name</FilterLabel>
                <FilterInput
                  value={filterName}
                  onChange={setFilterName}
                  placeholder="e.g., example-service"
                />
              </div>
              <div>
                <FilterLabel>Service ID</FilterLabel>
                <FilterInput
                  value={filterId}
                  onChange={setFilterId}
                  placeholder="Service ID"
                  mono
                />
              </div>
            </div>
            <div className="flex gap-2 mt-4">
              <button onClick={handleFilterApply}
                className="px-5 py-2 rounded-lg text-sm font-semibold"
                style={{ background: '#3b82f6', color: '#fff', border: 'none', cursor: 'pointer' }}
                onMouseEnter={e => e.currentTarget.style.background = '#2563eb'}
                onMouseLeave={e => e.currentTarget.style.background = '#3b82f6'}>
                Apply filters
              </button>
              <button onClick={handleFilterReset}
                className="px-5 py-2 rounded-lg text-sm font-medium"
                style={{ background: '#f8fafc', color: '#64748b', border: '1px solid #e2e8f0', cursor: 'pointer' }}
                onMouseEnter={e => e.currentTarget.style.background = '#f1f5f9'}
                onMouseLeave={e => e.currentTarget.style.background = '#f8fafc'}>
                Reset
              </button>
            </div>
          </div>
        </div>

        {/* Table */}
        {servicesLoading ? (
          <div className="flex items-center justify-center py-20">
            <div className="relative w-10 h-10">
              <div className="absolute inset-0 rounded-full border-2 border-blue-100"></div>
              <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-blue-500 animate-spin"></div>
            </div>
          </div>
        ) : services.length === 0 ? (
          <EmptyState onRegister={() => setShowRegister(true)} />
        ) : (
          <ServicesTable
            services={services}
            togglingId={togglingId}
            onToggle={handleToggle}
          />
        )}
      </main>

      {/* Register modal */}
      {showRegister && (
        <RegisterModal
          onClose={() => setShowRegister(false)}
          onSuccess={handleRegistered}
        />
      )}
    </PageShell>
  );
};

// ─── Services Table ───────────────────────────────────────────────────────────

const ServicesTable: React.FC<{
  services: ServiceEntry[];
  togglingId: string | null;
  onToggle: (service: ServiceEntry) => void;
}> = ({ services, togglingId, onToggle }) => {
  const formatDate = (dateString?: string) => {
    if (!dateString) return '—';
    const d = new Date(dateString);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) +
      ' ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
  };

  return (
    <div className="rounded-xl overflow-hidden" style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
      <div className="overflow-x-auto">
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
              {['Status', 'Name', 'ID', 'Registered', ''].map(h => (
                <th key={h} style={{
                  padding: '10px 16px', textAlign: 'left',
                  fontSize: '0.7rem', fontWeight: 600, color: '#94a3b8',
                  letterSpacing: '0.08em', textTransform: 'uppercase', whiteSpace: 'nowrap',
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {services.map((service, i) => {
              const isToggling = togglingId === service.id;
              return (
                <tr key={service.id}
                  style={{ borderBottom: i < services.length - 1 ? '1px solid #f1f5f9' : 'none' }}
                  onMouseEnter={e => (e.currentTarget.style.background = '#fafbff')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>

                  <td style={{ padding: '14px 16px', whiteSpace: 'nowrap' }}>
                    <StatusPill enabled={service.is_active} />
                  </td>

                  <td style={{ padding: '14px 16px' }}>
                    <div style={{ fontWeight: 600, fontSize: '0.875rem', color: '#1e293b' }}>{service.name}</div>
                    {service.description && (
                      <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '2px', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {service.description}
                      </div>
                    )}
                  </td>

                  <td style={{ padding: '14px 16px', fontFamily: 'monospace', fontSize: '0.775rem', color: '#64748b', whiteSpace: 'nowrap' }}>
                    {service.id}
                  </td>

                  <td style={{ padding: '14px 16px', fontFamily: 'monospace', fontSize: '0.75rem', color: '#94a3b8', whiteSpace: 'nowrap' }}>
                    {formatDate(service.created_at)}
                  </td>

                  <td style={{ padding: '14px 16px', whiteSpace: 'nowrap' }}>
                    <ToggleButton
                      enabled={service.is_active}
                      loading={isToggling}
                      onClick={() => onToggle(service)}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ─── Register Modal ───────────────────────────────────────────────────────────

const toSlug = (value: string) =>
  value.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');

const modalLabelStyle: React.CSSProperties = {
  display: 'block', fontSize: '0.75rem', fontWeight: 600,
  color: '#64748b', letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: '6px',
};

const RegisterModal: React.FC<{
  onClose: () => void;
  onSuccess: (name: string) => void;
}> = ({ onClose, onSuccess }) => {
  const [name, setName] = useState('');
  const [id, setId] = useState('');
  const [idTouched, setIdTouched] = useState(false);
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleNameChange = (value: string) => {
    setName(value);
    if (!idTouched) setId(toSlug(value));
  };

  const handleIdChange = (value: string) => {
    setIdTouched(true);
    setId(value.toLowerCase().replace(/[^a-z0-9-]/g, ''));
  };

  const canSubmit = name.trim().length > 0 && id.trim().length > 0 && !loading;

  const handleSubmit = async () => {
    const trimmedName = name.trim();
    const trimmedId = id.trim();
    if (!trimmedName) { setError('Service name is required.'); return; }
    if (!trimmedId)   { setError('Service ID is required.'); return; }
    try {
      setLoading(true);
      setError(null);
      await servicesAPI.registerService({
        id: trimmedId,
        name: trimmedName,
        description: description.trim() || undefined,
      });
      onSuccess(trimmedName);
    } catch (err: any) {
      console.error('Register failed:', err);
      const status = err?.response?.status ?? err?.status;
      if (status === 409) {
        setError('A service with this ID or name already exists.');
      } else if (status === 422) {
        const details = err?.response?.data?.details?.field_errors;
        const msg = details
          ? Object.entries(details).map(([k, v]) => `${k}: ${(v as string[]).join(', ')}`).join(' · ')
          : null;
        setError(msg ?? 'Validation error. Please check your inputs.');
      } else {
        setError('Failed to register service. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.4)', backdropFilter: 'blur(4px)' }}
      onClick={onClose}>
      <div
        className="w-full rounded-2xl shadow-2xl"
        style={{ maxWidth: '480px', background: '#fff', border: '1px solid #e2e8f0' }}
        onClick={e => e.stopPropagation()}>

        {/* Modal header */}
        <div className="flex items-center justify-between px-6 py-5" style={{ borderBottom: '1px solid #f1f5f9' }}>
          <div>
            <h2 style={{ fontSize: '1rem', fontWeight: 700, color: '#0f172a', letterSpacing: '-0.01em' }}>
              Register service
            </h2>
            <p style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: '2px' }}>
              Add a new service to the registry
            </p>
          </div>
          <button onClick={onClose}
            style={{ color: '#94a3b8', background: 'none', border: 'none', cursor: 'pointer', padding: '4px' }}
            onMouseEnter={e => e.currentTarget.style.color = '#475569'}
            onMouseLeave={e => e.currentTarget.style.color = '#94a3b8'}>
            <CloseXIcon />
          </button>
        </div>

        {/* Modal body */}
        <div className="px-6 py-5" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {error && <ErrorAlert message={error} onDismiss={() => setError(null)} />}

          <div>
            <label style={modalLabelStyle}>
              Name <span style={{ color: '#ef4444' }}>*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={e => handleNameChange(e.target.value)}
              placeholder="e.g., Example Service"
              maxLength={128}
              style={modalInputStyle}
              onFocus={e => { e.currentTarget.style.borderColor = '#3b82f6'; e.currentTarget.style.boxShadow = '0 0 0 3px rgba(59,130,246,0.1)'; }}
              onBlur={e => { e.currentTarget.style.borderColor = '#e2e8f0'; e.currentTarget.style.boxShadow = 'none'; }}
            />
          </div>

          <div>
            <label style={modalLabelStyle}>
              ID <span style={{ color: '#ef4444' }}>*</span>
              <span style={{ color: '#94a3b8', fontWeight: 400, textTransform: 'none', letterSpacing: 0, marginLeft: '6px' }}>
                auto-filled · lowercase, hyphens only
              </span>
            </label>
            <input
              type="text"
              value={id}
              onChange={e => handleIdChange(e.target.value)}
              placeholder="e.g., example-service"
              maxLength={64}
              style={{ ...modalInputStyle, fontFamily: 'monospace' }}
              onFocus={e => { e.currentTarget.style.borderColor = '#3b82f6'; e.currentTarget.style.boxShadow = '0 0 0 3px rgba(59,130,246,0.1)'; }}
              onBlur={e => { e.currentTarget.style.borderColor = '#e2e8f0'; e.currentTarget.style.boxShadow = 'none'; }}
              onKeyDown={e => { if (e.key === 'Enter') handleSubmit(); }}
            />
            {id && (
              <p style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '4px', fontFamily: 'monospace' }}>
                Will be registered as: <strong style={{ color: '#475569' }}>{id}</strong>
              </p>
            )}
          </div>

          <div>
            <label style={modalLabelStyle}>
              Description{' '}
              <span style={{ color: '#94a3b8', fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>optional</span>
            </label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Brief description of what this service does"
              rows={3}
              style={{ ...modalInputStyle, resize: 'vertical', minHeight: '72px' }}
              onFocus={e => { e.currentTarget.style.borderColor = '#3b82f6'; e.currentTarget.style.boxShadow = '0 0 0 3px rgba(59,130,246,0.1)'; }}
              onBlur={e => { e.currentTarget.style.borderColor = '#e2e8f0'; e.currentTarget.style.boxShadow = 'none'; }}
            />
          </div>
        </div>

        {/* Modal footer */}
        <div className="flex justify-end gap-2 px-6 py-4" style={{ borderTop: '1px solid #f1f5f9' }}>
          <button onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm font-medium"
            style={{ background: '#f8fafc', color: '#64748b', border: '1px solid #e2e8f0', cursor: 'pointer' }}
            onMouseEnter={e => e.currentTarget.style.background = '#f1f5f9'}
            onMouseLeave={e => e.currentTarget.style.background = '#f8fafc'}>
            Cancel
          </button>
          <button onClick={handleSubmit} disabled={!canSubmit}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold"
            style={{
              background: !canSubmit ? '#bfdbfe' : '#3b82f6',
              color: '#fff', border: 'none',
              cursor: !canSubmit ? 'not-allowed' : 'pointer',
            }}
            onMouseEnter={e => { if (canSubmit) e.currentTarget.style.background = '#2563eb'; }}
            onMouseLeave={e => { if (canSubmit) e.currentTarget.style.background = '#3b82f6'; }}>
            {loading ? (
              <>
                <div className="w-3.5 h-3.5 rounded-full border-2 border-white border-t-transparent animate-spin" />
                Registering...
              </>
            ) : (
              'Register service'
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

// ─── Small components ─────────────────────────────────────────────────────────

const StatusPill: React.FC<{ enabled: boolean }> = ({ enabled }) => (
  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full"
    style={{
      background: enabled ? '#f0fdf4' : '#f8fafc',
      border: `1px solid ${enabled ? '#bbf7d0' : '#e2e8f0'}`,
      color: enabled ? '#166534' : '#64748b',
      fontSize: '0.7rem',
      fontWeight: 600,
    }}>
    <span className="w-1.5 h-1.5 rounded-full flex-shrink-0"
      style={{ background: enabled ? '#10b981' : '#cbd5e1' }} />
    {enabled ? 'Active' : 'Disabled'}
  </span>
);

const ToggleButton: React.FC<{ enabled: boolean; loading: boolean; onClick: () => void }> = ({ enabled, loading, onClick }) => (
  <button onClick={onClick} disabled={loading}
    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
    style={{
      background: enabled ? '#fff1f2' : '#f0fdf4',
      color: enabled ? '#be123c' : '#166534',
      border: `1px solid ${enabled ? '#fecdd3' : '#bbf7d0'}`,
      cursor: loading ? 'wait' : 'pointer',
      opacity: loading ? 0.7 : 1,
      minWidth: '80px',
      justifyContent: 'center',
    }}
    onMouseEnter={e => { if (!loading) e.currentTarget.style.opacity = '0.8'; }}
    onMouseLeave={e => { if (!loading) e.currentTarget.style.opacity = '1'; }}>
    {loading ? (
      <div className="w-3 h-3 rounded-full border-2 border-current border-t-transparent animate-spin" />
    ) : enabled ? (
      <><DisableIcon /> Disable</>
    ) : (
      <><EnableIcon /> Enable</>
    )}
  </button>
);

const EmptyState: React.FC<{ onRegister: () => void }> = ({ onRegister }) => (
  <div className="rounded-xl p-14 text-center" style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
    <div style={{ width: '48px', height: '48px', margin: '0 auto 16px', borderRadius: '12px', background: '#f1f5f9', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
        <rect x="1.5" y="1.5" width="8" height="8" rx="2" stroke="#94a3b8" strokeWidth="1.5"/>
        <rect x="12.5" y="1.5" width="8" height="8" rx="2" stroke="#94a3b8" strokeWidth="1.5"/>
        <rect x="1.5" y="12.5" width="8" height="8" rx="2" stroke="#94a3b8" strokeWidth="1.5"/>
        <rect x="12.5" y="12.5" width="8" height="8" rx="2" stroke="#94a3b8" strokeWidth="1.5"/>
      </svg>
    </div>
    <p style={{ color: '#334155', fontSize: '0.95rem', fontWeight: 600, marginBottom: '4px' }}>No services registered</p>
    <p style={{ color: '#94a3b8', fontSize: '0.82rem', marginBottom: '20px' }}>
      Register your first service to start routing logs to it.
    </p>
    <button onClick={onRegister}
      className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold"
      style={{ background: '#3b82f6', color: '#fff', border: 'none', cursor: 'pointer' }}
      onMouseEnter={e => e.currentTarget.style.background = '#2563eb'}
      onMouseLeave={e => e.currentTarget.style.background = '#3b82f6'}>
      <PlusIcon />
      Register service
    </button>
  </div>
);

const FilterLabel: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748b', letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: '6px' }}>
    {children}
  </div>
);

const FilterInput: React.FC<{ value: string; onChange: (v: string) => void; placeholder: string; mono?: boolean }> = ({ value, onChange, placeholder, mono }) => (
  <input
    type="text"
    value={value}
    onChange={e => onChange(e.target.value)}
    placeholder={placeholder}
    style={{
      width: '100%', padding: '8px 12px',
      border: '1px solid #e2e8f0', borderRadius: '8px',
      fontSize: '0.875rem', color: '#1e293b', background: '#fff',
      outline: 'none', fontFamily: mono ? 'monospace' : 'inherit',
      boxSizing: 'border-box',
    }}
    onFocus={e => { e.currentTarget.style.borderColor = '#3b82f6'; e.currentTarget.style.boxShadow = '0 0 0 3px rgba(59,130,246,0.1)'; }}
    onBlur={e => { e.currentTarget.style.borderColor = '#e2e8f0'; e.currentTarget.style.boxShadow = 'none'; }}
  />
);

const modalInputStyle: React.CSSProperties = {
  width: '100%', padding: '9px 12px',
  border: '1px solid #e2e8f0', borderRadius: '8px',
  fontSize: '0.875rem', color: '#1e293b', background: '#fff',
  outline: 'none', transition: 'border-color 0.15s',
  boxSizing: 'border-box',
};

// ─── Icons ────────────────────────────────────────────────────────────────────

const PlusIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <path d="M7 2v10M2 7h10" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
  </svg>
);

const EnableIcon = () => (
  <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
    <path d="M2 5.5l2.5 2.5 4.5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

const DisableIcon = () => (
  <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
    <circle cx="5.5" cy="5.5" r="4" stroke="currentColor" strokeWidth="1.3"/>
    <path d="M3.5 3.5l4 4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
  </svg>
);

const CloseXIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
    <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
);