import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../services/authContext';
import { authAPI } from '../services/api';
import { LoadingSpinner, ErrorAlert } from '../components/Common';

export const Login: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [isLoadingUrl, setIsLoadingUrl] = useState(false);

  useEffect(() => {
    if (isAuthenticated && !isLoading) {
      navigate('/dashboard');
    }
  }, [isAuthenticated, isLoading, navigate]);

  const handleGitHubLogin = async () => {
    try {
      setIsLoadingUrl(true);
      setError(null);
      const loginUrl = await authAPI.getLoginUrl();
      window.location.href = loginUrl;
    } catch (err) {
      setError('Failed to get GitHub login URL. Please try again.');
      console.error('Login URL fetch failed:', err);
      setIsLoadingUrl(false);
    }
  };

  if (isLoading) {
    return <LoadingSpinner message="Checking authentication..." />;
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', background: '#0F1117' }}>
      {/* Left panel */}
      <div className="hidden lg:flex flex-col justify-between w-1/2 p-12"
        style={{ background: 'linear-gradient(160deg, #0f1117 0%, #151929 100%)', borderRight: '1px solid #1e2235' }}>
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-9 h-9 rounded-xl"
            style={{ background: 'linear-gradient(135deg, #3b82f6, #6366f1)' }}>
            <svg width="18" height="18" viewBox="0 0 16 16" fill="none">
              <rect x="2" y="3" width="12" height="1.5" rx="0.75" fill="white" opacity="0.9"/>
              <rect x="2" y="7" width="8" height="1.5" rx="0.75" fill="white" opacity="0.7"/>
              <rect x="2" y="11" width="10" height="1.5" rx="0.75" fill="white" opacity="0.5"/>
            </svg>
          </div>
          <span style={{ color: '#e2e8f0', fontWeight: 700, fontSize: '1.1rem', letterSpacing: '-0.02em' }}>LMS</span>
        </div>

        <div>
          <div style={{ color: '#3b82f6', fontSize: '0.75rem', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '16px' }}>
            Log Management System
          </div>
          <h2 style={{ color: '#e2e8f0', fontSize: '2.4rem', fontWeight: 700, lineHeight: 1.2, letterSpacing: '-0.03em', marginBottom: '20px' }}>
            Centralized log<br />ingestion & querying
          </h2>
          <p style={{ color: '#64748b', fontSize: '0.95rem', lineHeight: 1.7, maxWidth: '360px' }}>
            A unified interface for monitoring application and audit logs — with filtering, export, and real-time health metrics.
          </p>

          <div className="mt-12 space-y-4">
            {[
              { label: 'App & audit logs', desc: 'Query both log types in one view' },
              { label: 'Health monitoring', desc: 'Database, cache, and uptime metrics' },
              { label: 'Export', desc: 'Download logs as JSON or CSV' },
            ].map(({ label, desc }) => (
              <div key={label} className="flex items-start gap-3">
                <div className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
                  style={{ background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.3)' }}>
                  <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                    <path d="M2 5l2 2 4-4" stroke="#3b82f6" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>
                <div>
                  <div style={{ color: '#cbd5e1', fontSize: '0.85rem', fontWeight: 600 }}>{label}</div>
                  <div style={{ color: '#475569', fontSize: '0.8rem' }}>{desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div style={{ color: '#334155', fontSize: '0.75rem' }}>
          Personal use only · GitHub OAuth 2.0
        </div>
      </div>

      {/* Right panel */}
      <div className="flex flex-1 items-center justify-center p-8">
        <div style={{ width: '100%', maxWidth: '400px' }}>
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-2 mb-10">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg"
              style={{ background: 'linear-gradient(135deg, #3b82f6, #6366f1)' }}>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <rect x="2" y="3" width="12" height="1.5" rx="0.75" fill="white" opacity="0.9"/>
                <rect x="2" y="7" width="8" height="1.5" rx="0.75" fill="white" opacity="0.7"/>
                <rect x="2" y="11" width="10" height="1.5" rx="0.75" fill="white" opacity="0.5"/>
              </svg>
            </div>
            <span style={{ color: '#e2e8f0', fontWeight: 700, letterSpacing: '-0.02em' }}>LMS</span>
          </div>

          <h1 style={{ color: '#e2e8f0', fontSize: '1.75rem', fontWeight: 700, letterSpacing: '-0.02em', marginBottom: '8px' }}>
            Sign in
          </h1>
          <p style={{ color: '#475569', fontSize: '0.9rem', marginBottom: '32px' }}>
            Authenticate with your GitHub account to continue.
          </p>

          {error && <ErrorAlert message={error} onDismiss={() => setError(null)} />}

          <button onClick={handleGitHubLogin} disabled={isLoadingUrl}
            className="w-full flex items-center justify-center gap-3 py-3 rounded-xl font-semibold transition-all"
            style={{
              background: isLoadingUrl ? '#1e2235' : '#fff',
              color: isLoadingUrl ? '#475569' : '#1e293b',
              border: '1px solid',
              borderColor: isLoadingUrl ? '#2d3656' : '#e2e8f0',
              fontSize: '0.9rem',
              cursor: isLoadingUrl ? 'not-allowed' : 'pointer',
            }}
            onMouseEnter={e => { if (!isLoadingUrl) e.currentTarget.style.borderColor = '#3b82f6'; }}
            onMouseLeave={e => { if (!isLoadingUrl) e.currentTarget.style.borderColor = '#e2e8f0'; }}>
            {isLoadingUrl ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2" style={{ borderColor: '#3b82f6' }}></div>
                Redirecting to GitHub...
              </>
            ) : (
              <>
                <GitHubIcon />
                Continue with GitHub
              </>
            )}
          </button>

          <div className="mt-6 rounded-xl p-4" style={{ background: '#131722', border: '1px solid #1e2235' }}>
            <p style={{ color: '#475569', fontSize: '0.75rem', lineHeight: 1.6 }}>
              <span style={{ color: '#64748b', fontWeight: 600 }}>Restricted access.</span>{' '}
              This system is configured for a single authorized user. Authentication is handled via GitHub OAuth 2.0.
            </p>
          </div>

          <p style={{ color: '#334155', fontSize: '0.72rem', textAlign: 'center', marginTop: '24px' }}>
            You'll be redirected to GitHub to complete sign-in.
          </p>
        </div>
      </div>
    </div>
  );
};

const GitHubIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="#1e293b">
    <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/>
  </svg>
);