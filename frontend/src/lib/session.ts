// Session tokens live in localStorage so every tab shares one session.
const KEY = 'lms.session'
const EVENT = 'lms:session'

export interface Session {
  accessToken: string
  refreshToken: string
  username: string
  /** epoch ms when the access token expires */
  expiresAt: number
}

export function readSession(): Session | null {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? (JSON.parse(raw) as Session) : null
  } catch {
    return null
  }
}

export function writeSession(session: Session | null): void {
  try {
    if (session) localStorage.setItem(KEY, JSON.stringify(session))
    else localStorage.removeItem(KEY)
  } catch {
    /* storage unavailable (private mode) — session lives for this page only */
  }
  window.dispatchEvent(new CustomEvent(EVENT))
}

export function onSessionChange(listener: () => void): () => void {
  const onStorage = (e: StorageEvent) => {
    if (e.key === KEY) listener()
  }
  window.addEventListener(EVENT, listener)
  window.addEventListener('storage', onStorage)
  return () => {
    window.removeEventListener(EVENT, listener)
    window.removeEventListener('storage', onStorage)
  }
}

// Drop any v1 keys so an upgrade starts from a clean slate.
for (const legacy of ['lms_access_token', 'lms_refresh_token', 'lms_username', 'lms_jti']) {
  try {
    localStorage.removeItem(legacy)
  } catch {
    /* ignore */
  }
}
