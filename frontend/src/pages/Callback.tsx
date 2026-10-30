import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { api, toSession } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Logo } from '../components/Shell'
import { Button, ErrorBanner } from '../components/ui'

export function Callback() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { signIn } = useAuth()
  const [error, setError] = useState<unknown>(null)
  const started = useRef(false)

  useEffect(() => {
    // The OAuth code is single-use: guard against StrictMode's double effect.
    if (started.current) return
    started.current = true
    const code = params.get('code')
    const state = params.get('state')
    const denied = params.get('error_description') ?? params.get('error')
    if (denied || !code || !state) {
      queueMicrotask(() => setError(new Error(denied ?? 'GitHub did not return an authorization code.')))
      return
    }
    api
      .callback(code, state)
      .then((tokens) => {
        signIn(toSession(tokens))
        navigate('/', { replace: true })
      })
      .catch(setError)
  }, [params, navigate, signIn])

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-sm animate-rise-in rounded-[var(--radius-lg)] border border-[var(--color-border-subtle)] bg-[var(--color-bg-raised)] p-7">
        <Logo size={32} />
        {error ? (
          <>
            <h1 className="mt-5 font-display text-lg font-medium">Sign-in failed</h1>
            <div className="mt-4">
              <ErrorBanner error={error} />
            </div>
            <Link to="/login" className="mt-5 block">
              <Button className="w-full">Back to sign in</Button>
            </Link>
          </>
        ) : (
          <>
            <h1 className="mt-5 font-display text-lg font-medium">Verifying with GitHub</h1>
            <p className="mt-2 flex items-center gap-2 text-sm text-[var(--color-text-muted)]">
              <Loader2 className="size-4 animate-spin text-[var(--color-amber)]" /> Checking your account…
            </p>
          </>
        )}
      </div>
    </div>
  )
}
