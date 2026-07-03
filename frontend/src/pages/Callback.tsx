import React, { useEffect, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { useAuth } from '../services/authContext';
import { authAPI } from '../services/api';
import { getJTIFromToken } from '../utils/storage';
import { ErrorAlert } from '../components/Common';

export interface CallbackError {
  error_code: string;
  message: string;
  request_id: string;
  details?: Record<string, null> | null;
}

export const Callback: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { login } = useAuth();
  
  // Guard ref ensures the mutation is absolutely triggered only once per mount
  const standardGuard = useRef(false);

  const code = searchParams.get('code');
  const state = searchParams.get('state');

  const { mutate, error: mutationError } = useMutation({
    mutationFn: async () => {
      if (!code || !state) {
        throw new Error('Missing authorization code or state. Please try again.');
      }
      return await authAPI.callback(code, state);
    },
    onSuccess: (tokenResponse) => {
      const jti = getJTIFromToken(tokenResponse.access_token) || '';

      if (tokenResponse.username !== 'Sanjaa46') {
        throw new Error(`Access denied. Only user 'Sanjaa46' is authorized. You are logged in as '${tokenResponse.username}'.`);
      }

      login(tokenResponse.access_token, tokenResponse.refresh_token, tokenResponse.username, jti);
      setTimeout(() => navigate('/dashboard'), 500);
    },
    onError: (err: CallbackError) => {
      console.error('Callback error:', err.message);
      setTimeout(() => navigate('/'), err.message?.includes('Access denied') ? 5000 : 3000);
    },
  });

  useEffect(() => {
    if (standardGuard.current) return;
    standardGuard.current = true;

    mutate();
  }, [mutate]);

  // Determine error message if any part of the mutation failed
  const errorMessage = mutationError ? mutationError.message : null;

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0F1117', padding: '16px' }}>
      <div className="rounded-2xl w-full p-8" style={{ maxWidth: '420px', background: '#131722', border: '1px solid #1e2235' }}>
        {errorMessage ? (
          <>
            <ErrorAlert message={errorMessage} />
            <p style={{ textAlign: 'center', color: '#475569', fontSize: '0.85rem', marginTop: '16px' }}>
              Redirecting to login...
            </p>
          </>
        ) : (
          <div className="flex flex-col items-center gap-4 py-4">
            <div className="relative w-12 h-12">
              <div className="absolute inset-0 rounded-full border-2" style={{ borderColor: 'rgba(59,130,246,0.15)' }}></div>
              <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-blue-500 animate-spin"></div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <p style={{ color: '#e2e8f0', fontWeight: 600, fontSize: '0.95rem', marginBottom: '4px' }}>
                Completing authentication
              </p>
              <p style={{ color: '#475569', fontSize: '0.82rem' }}>
                Verifying your GitHub credentials...
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};