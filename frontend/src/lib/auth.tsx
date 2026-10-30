import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from './api'
import { onSessionChange, readSession, writeSession, type Session } from './session'

interface AuthState {
  session: Session | null
  signIn: (session: Session) => void
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  // An expired *access* token is fine: the refresh token renews it on the
  // first request. Only a missing/revoked refresh token means "signed out".
  const [session, setSession] = useState<Session | null>(() => readSession())
  const queryClient = useQueryClient()

  useEffect(() => onSessionChange(() => setSession(readSession())), [])

  const signIn = useCallback((next: Session) => writeSession(next), [])

  const signOut = useCallback(async () => {
    try {
      await api.logout()
    } catch {
      /* already invalid server-side — clear locally regardless */
    }
    writeSession(null)
    queryClient.clear()
  }, [queryClient])

  const value = useMemo(() => ({ session, signIn, signOut }), [session, signIn, signOut])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
