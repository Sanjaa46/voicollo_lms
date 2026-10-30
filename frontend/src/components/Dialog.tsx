import { useEffect, useRef, type ReactNode } from 'react'
import { X } from 'lucide-react'
import { IconButton } from './ui'

/** Accessible modal built on <dialog> (focus trap + Esc handled by the browser). */
export function Dialog({
  open,
  title,
  description,
  onClose,
  children,
  footer,
  wide = false,
}: {
  open: boolean
  title: string
  description?: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  wide?: boolean
}) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (open && !el.open) el.showModal()
    if (!open && el.open) el.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      className={`m-auto ${wide ? 'w-[min(760px,calc(100vw-32px))]' : 'w-[min(520px,calc(100vw-32px))]'} rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-raised)] p-0 text-[var(--color-text)] shadow-[var(--shadow-lg)] backdrop:bg-black/60 backdrop:backdrop-blur-[2px] open:animate-rise-in`}
    >
      {open && (
        <div>
          <div className="flex items-start justify-between gap-4 border-b border-[var(--color-border-subtle)] px-5 py-4">
            <div>
              <h2 className="font-display text-base font-medium tracking-tight">{title}</h2>
              {description && <p className="mt-1 text-xs text-[var(--color-text-faint)]">{description}</p>}
            </div>
            <IconButton label="Close" onClick={onClose}>
              <X className="size-4" />
            </IconButton>
          </div>
          <div className="px-5 py-4">{children}</div>
          {footer && (
            <div className="flex justify-end gap-2 border-t border-[var(--color-border-subtle)] px-5 py-3">{footer}</div>
          )}
        </div>
      )}
    </dialog>
  )
}
