import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../services/authContext';
import { authAPI } from '../services/api';

export const Sidebar: React.FC = () => {
  const { username, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleLogout = async () => {
    try {
      await authAPI.logout();
      logout();
      navigate('/');
    } catch {
      logout();
      navigate('/');
    }
  };

  const isActive = (path: string) => location.pathname === path;

  const navItems = [
    { path: '/dashboard', icon: LogsIcon, label: 'Logs' },
    { path: '/services', icon: ServicesIcon, label: 'Services' },
    { path: '/health', icon: HealthIcon, label: 'Health' },
  ];

  return (
    <>
      {/* Mobile top bar */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-4 h-14"
        style={{ background: '#0F1117', borderBottom: '1px solid #1e2235' }}>
        <div className="flex items-center gap-2 cursor-pointer" onClick={() => navigate('/dashboard')}>
          <LogoMark />
          <span style={{ color: '#e2e8f0', fontWeight: 700, fontSize: '1rem', letterSpacing: '-0.02em' }}>LMS</span>
        </div>
        <button onClick={() => setMobileOpen(!mobileOpen)} style={{ color: '#94a3b8' }}>
          {mobileOpen ? <CloseIcon /> : <MenuIcon />}
        </button>
      </div>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-40 pt-14" style={{ background: 'rgba(0,0,0,0.7)' }} onClick={() => setMobileOpen(false)}>
          <div className="w-64 h-full p-4 flex flex-col gap-2" style={{ background: '#0F1117' }} onClick={e => e.stopPropagation()}>
            {navItems.map(({ path, icon: Icon, label }) => (
              <button key={path} onClick={() => { navigate(path); setMobileOpen(false); }}
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg w-full text-left transition-all"
                style={{
                  background: isActive(path) ? '#1c2340' : 'transparent',
                  color: isActive(path) ? '#3b82f6' : '#94a3b8',
                  fontWeight: isActive(path) ? 600 : 400,
                  fontSize: '0.875rem',
                }}>
                <Icon active={isActive(path)} />
                {label}
              </button>
            ))}
            <div className="mt-auto">
              <div className="flex items-center gap-2 px-3 py-2 mb-2" style={{ color: '#64748b', fontSize: '0.75rem' }}>
                <AvatarIcon />
                <span style={{ color: '#94a3b8' }}>{username}</span>
              </div>
              <button onClick={handleLogout} className="flex items-center gap-3 px-3 py-2.5 rounded-lg w-full text-left transition-all"
                style={{ color: '#ef4444', fontSize: '0.875rem' }}>
                <LogoutIcon />
                Sign out
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Desktop sidebar */}
      <aside className="hidden md:flex flex-col fixed left-0 top-0 h-full w-56 z-30"
        style={{ background: '#0F1117', borderRight: '1px solid #1e2235' }}>

        {/* Logo */}
        <div className="flex items-center gap-2.5 px-5 h-16 cursor-pointer flex-shrink-0"
          onClick={() => navigate('/dashboard')}
          style={{ borderBottom: '1px solid #1e2235' }}>
          <LogoMark />
          <div>
            <div style={{ color: '#e2e8f0', fontWeight: 700, fontSize: '1rem', letterSpacing: '-0.02em', lineHeight: 1 }}>LMS</div>
            <div style={{ color: '#475569', fontSize: '0.65rem', marginTop: 2, fontFamily: 'monospace' }}>log management</div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 flex flex-col gap-1 px-3 py-4">
          <div style={{ color: '#334155', fontSize: '0.65rem', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', padding: '0 8px 8px' }}>
            Navigation
          </div>
          {navItems.map(({ path, icon: Icon, label }) => (
            <button key={path} onClick={() => navigate(path)}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg w-full text-left transition-all"
              style={{
                background: isActive(path) ? 'rgba(59,130,246,0.12)' : 'transparent',
                color: isActive(path) ? '#60a5fa' : '#64748b',
                fontWeight: isActive(path) ? 600 : 400,
                fontSize: '0.875rem',
                border: isActive(path) ? '1px solid rgba(59,130,246,0.2)' : '1px solid transparent',
              }}>
              <Icon active={isActive(path)} />
              {label}
            </button>
          ))}
        </nav>

        {/* User */}
        <div style={{ borderTop: '1px solid #1e2235', padding: '12px' }}>
          <div className="flex items-center gap-2 px-2 py-2 rounded-lg mb-1"
            style={{ background: '#131722' }}>
            <div className="flex items-center justify-center w-7 h-7 rounded-full flex-shrink-0"
              style={{ background: 'linear-gradient(135deg, #3b82f6, #6366f1)', fontSize: '0.7rem', color: '#fff', fontWeight: 700 }}>
              {username?.charAt(0).toUpperCase()}
            </div>
            <span style={{ color: '#94a3b8', fontSize: '0.8rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {username}
            </span>
          </div>
          <button onClick={handleLogout} className="flex items-center gap-2 w-full px-2 py-2 rounded-lg transition-all"
            style={{ color: '#64748b', fontSize: '0.8rem' }}
            onMouseEnter={e => (e.currentTarget.style.color = '#ef4444')}
            onMouseLeave={e => (e.currentTarget.style.color = '#64748b')}>
            <LogoutIcon />
            Sign out
          </button>
        </div>
      </aside>
    </>
  );
};

// Keep Header as alias for backward compat (pages import Header)
export const Header = Sidebar;

export const PageShell: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div style={{ minHeight: '100vh', background: '#f8fafc' }}>
    <Sidebar />
    <div className="md:pl-56 pt-14 md:pt-0">
      {children}
    </div>
  </div>
);

export const LoadingSpinner: React.FC<{ message?: string }> = ({ message = 'Loading...' }) => (
  <div className="flex flex-col items-center justify-center min-h-screen" style={{ background: '#f8fafc' }}>
    <div className="relative w-12 h-12">
      <div className="absolute inset-0 rounded-full border-2 border-blue-100"></div>
      <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-blue-500 animate-spin"></div>
    </div>
    <p className="mt-4 text-sm" style={{ color: '#64748b' }}>{message}</p>
  </div>
);

export const ErrorAlert: React.FC<{ message: string; onDismiss?: () => void }> = ({ message, onDismiss }) => (
  <div className="flex items-start justify-between gap-4 rounded-xl px-4 py-3 mb-4"
    style={{ background: '#fff1f2', border: '1px solid #fecdd3' }}>
    <div className="flex items-start gap-3">
      <span style={{ color: '#ef4444', fontSize: '1rem', marginTop: '1px', flexShrink: 0 }}>⚠</span>
      <p style={{ color: '#be123c', fontSize: '0.875rem' }}>{message}</p>
    </div>
    {onDismiss && (
      <button onClick={onDismiss} style={{ color: '#f87171', flexShrink: 0 }}>✕</button>
    )}
  </div>
);

export const SuccessAlert: React.FC<{ message: string; onDismiss?: () => void }> = ({ message, onDismiss }) => (
  <div className="flex items-start justify-between gap-4 rounded-xl px-4 py-3 mb-4"
    style={{ background: '#f0fdf4', border: '1px solid #bbf7d0' }}>
    <div className="flex items-start gap-3">
      <span style={{ color: '#10b981', fontSize: '1rem', marginTop: '1px', flexShrink: 0 }}>✓</span>
      <p style={{ color: '#065f46', fontSize: '0.875rem' }}>{message}</p>
    </div>
    {onDismiss && (
      <button onClick={onDismiss} style={{ color: '#34d399', flexShrink: 0 }}>✕</button>
    )}
  </div>
);

export const InfoAlert: React.FC<{ message: string; onDismiss?: () => void }> = ({ message, onDismiss }) => (
  <div className="flex items-start justify-between gap-4 rounded-xl px-4 py-3 mb-4"
    style={{ background: '#eff6ff', border: '1px solid #bfdbfe' }}>
    <div className="flex items-start gap-3">
      <span style={{ color: '#3b82f6', fontSize: '1rem', marginTop: '1px', flexShrink: 0 }}>ℹ</span>
      <p style={{ color: '#1e40af', fontSize: '0.875rem' }}>{message}</p>
    </div>
    {onDismiss && (
      <button onClick={onDismiss} style={{ color: '#60a5fa', flexShrink: 0 }}>✕</button>
    )}
  </div>
);

interface PaginationProps {
  page: number;
  hasNext: boolean;
  onPrevious: () => void;
  onNext: () => void;
}

export const Pagination: React.FC<PaginationProps> = ({ page, hasNext, onPrevious, onNext }) => (
  <div className="flex items-center justify-between mt-6">
    <button onClick={onPrevious} disabled={page === 1}
      className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all"
      style={{
        background: page === 1 ? '#f1f5f9' : '#fff',
        color: page === 1 ? '#cbd5e1' : '#475569',
        border: '1px solid',
        borderColor: page === 1 ? '#e2e8f0' : '#e2e8f0',
        cursor: page === 1 ? 'not-allowed' : 'pointer',
      }}>
      ← Previous
    </button>
    <span style={{ color: '#64748b', fontSize: '0.875rem' }}>
      Page <strong style={{ color: '#1e293b' }}>{page}</strong>
    </span>
    <button onClick={onNext} disabled={!hasNext}
      className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all"
      style={{
        background: !hasNext ? '#f1f5f9' : '#3b82f6',
        color: !hasNext ? '#cbd5e1' : '#fff',
        border: '1px solid',
        borderColor: !hasNext ? '#e2e8f0' : '#3b82f6',
        cursor: !hasNext ? 'not-allowed' : 'pointer',
      }}>
      Next →
    </button>
  </div>
);

interface BadgeProps {
  level?: string;
  outcome?: string;
  children: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({ level, outcome, children }) => {
  let style = { bg: '#f1f5f9', text: '#475569', dot: '#94a3b8' };

  if (level) {
    switch (level) {
      case 'DEBUG': style = { bg: '#f1f5f9', text: '#475569', dot: '#94a3b8' }; break;
      case 'INFO':  style = { bg: '#eff6ff', text: '#2563eb', dot: '#3b82f6' }; break;
      case 'WARN':  style = { bg: '#fffbeb', text: '#b45309', dot: '#f59e0b' }; break;
      case 'ERROR': style = { bg: '#fff1f2', text: '#be123c', dot: '#ef4444' }; break;
      case 'FATAL': style = { bg: '#faf5ff', text: '#7e22ce', dot: '#a855f7' }; break;
    }
  }
  if (outcome) {
    switch (outcome) {
      case 'SUCCESS': style = { bg: '#f0fdf4', text: '#166534', dot: '#10b981' }; break;
      case 'FAILURE': style = { bg: '#fff1f2', text: '#be123c', dot: '#ef4444' }; break;
      case 'PARTIAL': style = { bg: '#fffbeb', text: '#b45309', dot: '#f59e0b' }; break;
    }
  }

  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full"
      style={{ background: style.bg, color: style.text, fontSize: '0.7rem', fontWeight: 600, letterSpacing: '0.03em' }}>
      <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: style.dot }}></span>
      {children}
    </span>
  );
};

// Icon components
const LogoMark = () => (
  <div className="flex items-center justify-center w-8 h-8 rounded-lg flex-shrink-0"
    style={{ background: 'linear-gradient(135deg, #3b82f6 0%, #6366f1 100%)' }}>
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="2" y="3" width="12" height="1.5" rx="0.75" fill="white" opacity="0.9"/>
      <rect x="2" y="7" width="8" height="1.5" rx="0.75" fill="white" opacity="0.7"/>
      <rect x="2" y="11" width="10" height="1.5" rx="0.75" fill="white" opacity="0.5"/>
    </svg>
  </div>
);

const LogsIcon = ({ active }: { active: boolean }) => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ flexShrink: 0 }}>
    <rect x="1.5" y="2" width="13" height="12" rx="2" stroke={active ? '#60a5fa' : '#475569'} strokeWidth="1.5"/>
    <path d="M4 5.5h8M4 8h6M4 10.5h7" stroke={active ? '#60a5fa' : '#475569'} strokeWidth="1.2" strokeLinecap="round"/>
  </svg>
);

const ServicesIcon = ({ active }: { active: boolean }) => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ flexShrink: 0 }}>
    <rect x="1.5" y="1.5" width="5.5" height="5.5" rx="1.5" stroke={active ? '#60a5fa' : '#475569'} strokeWidth="1.3"/>
    <rect x="9" y="1.5" width="5.5" height="5.5" rx="1.5" stroke={active ? '#60a5fa' : '#475569'} strokeWidth="1.3"/>
    <rect x="1.5" y="9" width="5.5" height="5.5" rx="1.5" stroke={active ? '#60a5fa' : '#475569'} strokeWidth="1.3"/>
    <rect x="9" y="9" width="5.5" height="5.5" rx="1.5" stroke={active ? '#60a5fa' : '#475569'} strokeWidth="1.3"/>
  </svg>
);

const HealthIcon = ({ active }: { active: boolean }) => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ flexShrink: 0 }}>
    <path d="M8 14s-6-4-6-8a4 4 0 0 1 6-3.46A4 4 0 0 1 14 6c0 4-6 8-6 8z" stroke={active ? '#60a5fa' : '#475569'} strokeWidth="1.5" fill="none"/>
    <path d="M5 8h2l1-2 1.5 4 1-2H13" stroke={active ? '#60a5fa' : '#475569'} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

const AvatarIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <circle cx="7" cy="5" r="2.5" stroke="#64748b" strokeWidth="1.2"/>
    <path d="M2 12c0-2.76 2.24-5 5-5s5 2.24 5 5" stroke="#64748b" strokeWidth="1.2" strokeLinecap="round"/>
  </svg>
);

const LogoutIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <path d="M5 2H2.5A1.5 1.5 0 0 0 1 3.5v7A1.5 1.5 0 0 0 2.5 12H5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    <path d="M9 4.5l3 2.5-3 2.5M5 7h7" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

const MenuIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
    <path d="M3 5h14M3 10h14M3 15h14" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
);

const CloseIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
    <path d="M5 5l10 10M15 5L5 15" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
);