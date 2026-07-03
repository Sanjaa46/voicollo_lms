// Token storage utilities
const ACCESS_TOKEN_KEY = 'lms_access_token';
const REFRESH_TOKEN_KEY = 'lms_refresh_token';
const USERNAME_KEY = 'lms_username';
const JTI_KEY = 'lms_jti';

export const storage = {
  // Access Token
  getAccessToken: (): string | null => {
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  },
  setAccessToken: (token: string): void => {
    localStorage.setItem(ACCESS_TOKEN_KEY, token);
  },
  clearAccessToken: (): void => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
  },

  // Refresh Token
  getRefreshToken: (): string | null => {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  },
  setRefreshToken: (token: string): void => {
    localStorage.setItem(REFRESH_TOKEN_KEY, token);
  },
  clearRefreshToken: (): void => {
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  },

  // Username
  getUsername: (): string | null => {
    return localStorage.getItem(USERNAME_KEY);
  },
  setUsername: (username: string): void => {
    localStorage.setItem(USERNAME_KEY, username);
  },
  clearUsername: (): void => {
    localStorage.removeItem(USERNAME_KEY);
  },

  // JTI (JWT ID claim for refresh token rotation)
  getJTI: (): string | null => {
    return localStorage.getItem(JTI_KEY);
  },
  setJTI: (jti: string): void => {
    localStorage.setItem(JTI_KEY, jti);
  },
  clearJTI: (): void => {
    localStorage.removeItem(JTI_KEY);
  },

  // Clear all
  clearAll: (): void => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(USERNAME_KEY);
    localStorage.removeItem(JTI_KEY);
  },
};

// Decode JWT payload (without verification)
export interface JWTPayload {
  sub?: string;
  exp?: number;
  iat?: number;
  jti?: string;
}

export const decodeJWT = (token: string): JWTPayload | null => {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;

    // 1. Replace URL-safe Base64 characters with standard Base64 characters
    const base64Url = parts[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');

    // 2. Decode safely handling multi-byte UTF-8 characters
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );

    return JSON.parse(jsonPayload);
  } catch {
    return null;
  }
};

// Check if token is expired
export const isTokenExpired = (token: string): boolean => {
  const decoded = decodeJWT(token);
  if (!decoded || !decoded.exp) return true;
  return decoded.exp * 1000 < Date.now();
};

// Extract JTI from token
export const getJTIFromToken = (token: string): string | null => {
  const decoded = decodeJWT(token);
  return decoded?.jti as string || null;
};
