import type { ReactNode } from 'react'

/** Read-only, syntax-coloured JSON (no dependencies, safe: renders text only). */
export function JsonView({ value }: { value: unknown }) {
  return (
    <pre className="max-h-[420px] overflow-auto rounded-[var(--radius-md)] border border-[var(--color-border-subtle)] bg-[var(--color-bg)] p-3 font-mono text-[12px] leading-relaxed">
      {render(value, 0)}
    </pre>
  )
}

function render(value: unknown, depth: number): ReactNode {
  const indent = '  '.repeat(depth)
  const inner = '  '.repeat(depth + 1)
  if (value === null) return <span className="text-[var(--color-text-faint)]">null</span>
  if (typeof value === 'string') return <span className="text-[var(--color-success)]">"{value}"</span>
  if (typeof value === 'number') return <span className="text-[var(--color-info)]">{value}</span>
  if (typeof value === 'boolean') return <span className="text-[var(--color-warning)]">{String(value)}</span>
  if (Array.isArray(value)) {
    if (!value.length) return '[]'
    return (
      <>
        {'[\n'}
        {value.map((item, i) => (
          <span key={i}>
            {inner}
            {render(item, depth + 1)}
            {i < value.length - 1 ? ',\n' : '\n'}
          </span>
        ))}
        {indent}]
      </>
    )
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
    if (!entries.length) return '{}'
    return (
      <>
        {'{\n'}
        {entries.map(([k, v], i) => (
          <span key={k}>
            {inner}
            <span className="text-[var(--color-accent-text)]">"{k}"</span>: {render(v, depth + 1)}
            {i < entries.length - 1 ? ',\n' : '\n'}
          </span>
        ))}
        {indent}
        {'}'}
      </>
    )
  }
  return String(value)
}
