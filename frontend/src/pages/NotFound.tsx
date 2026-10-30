import { Link } from 'react-router-dom'
import { Button } from '../components/ui'

export function NotFound() {
  return (
    <div className="flex flex-col items-start gap-4 py-20">
      <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-accent-text)]">404</p>
      <h1 className="font-display text-3xl font-medium tracking-tight">Nothing logged here.</h1>
      <Link to="/">
        <Button>Back to overview</Button>
      </Link>
    </div>
  )
}
