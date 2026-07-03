import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { storage, isTokenExpired } from '../utils/storage';

interface AuthContextType {
  isAuthenticated: boolean;
  username: string | null;
  isLoading: boolean;
  login: (accessToken: string, refreshToken: string, username: string, jti: string) => void;
  logout: () => void;
  checkAuth: () => Promise<boolean>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [username, setUsername] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Check stored credentials on mount
  useEffect(() => {
    const checkStoredAuth = () => {
      const storedToken = storage.getAccessToken();
      const storedUsername = storage.getUsername();

      if (storedToken && storedUsername) {
        if (!isTokenExpired(storedToken)) {
          setIsAuthenticated(true);
          setUsername(storedUsername);
        } else {
          // Token expired, clear storage
          storage.clearAll();
        }
      }
      setIsLoading(false);
    };

    checkStoredAuth();
  }, []);

  const login = useCallback(
    (accessToken: string, refreshToken: string, user: string, jti: string) => {
      storage.setAccessToken(accessToken);
      storage.setRefreshToken(refreshToken);
      storage.setUsername(user);
      storage.setJTI(jti);
      setIsAuthenticated(true);
      setUsername(user);
    },
    []
  );

  const logout = useCallback(() => {
    storage.clearAll();
    setIsAuthenticated(false);
    setUsername(null);
  }, []);

  const checkAuth = useCallback(async (): Promise<boolean> => {
    const token = storage.getAccessToken();
    if (!token) {
      return false;
    }
    if (isTokenExpired(token)) {
      logout();
      return false;
    }
    return true;
  }, [logout]);

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        username,
        isLoading,
        login,
        logout,
        checkAuth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
