import { useState } from 'react'
import { Link } from 'react-router-dom'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Code2, Pencil, Plus, Power, Search, ShieldCheck } from 'lucide-react'
import { ApiError, api } from '../lib/api'
import { integer, relativeTime } from '../lib/format'
import type { Service } from '../lib/types'
import { Dialog } from '../components/Dialog'
import {
  Button,
  CopyButton,
  EmptyState,
  ErrorBanner,
  Field,
  IconButton,
  Input,
  PageHeader,
  Panel,
  Segmented,
  Spinner,
  Textarea,
} from '../components/ui'
import { cn } from '../lib/cn'

type StatusFilter = 'all' | 'active' | 'disabled'

export function Services() {
  const [q, setQ] = useState('')
  const [status, setStatus] = useState<StatusFilter>('all')
  const [editing, setEditing] = useState<Service | 'new' | null>(null)
  const [integrating, setIntegrating] = useState<Service | null>(null)
  const [confirming, setConfirming] = useState<Service | null>(null)
  const queryClient = useQueryClient()

  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ['services', q, status],
    queryFn: () => api.services({ q: q || undefined, status: status === 'all' ? undefined : status }),
    placeholderData: keepPreviousData,
    refetchInterval: 60_000,
  })

  const toggle = useMutation({
    mutationFn: (s: Service) => api.setServiceActive(s.id, !s.is_active),
    onSuccess: () => {
      setConfirming(null)
      void queryClient.invalidateQueries({ queryKey: ['services'] })
    },
  })

  return (
    <>
      <PageHeader eyebrow="Services" title="Producers">
        <Button variant="primary" icon={<Plus className="size-4" />} onClick={() => setEditing('new')}>
          Register service
        </Button>
      </PageHeader>

      <Panel className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-3 border-b border-[var(--color-border-subtle)] p-3">
          <div className="relative min-w-[220px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[var(--color-text-faint)]" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by id or name" className="pl-9" />
          </div>
          <Segmented
            label="Status"
            value={status}
            onChange={setStatus}
            options={[
              { value: 'all', label: 'All' },
              { value: 'active', label: 'Active' },
              { value: 'disabled', label: 'Disabled' },
            ]}
          />
        </div>

        {error ? (
          <div className="p-4">
            <ErrorBanner error={error} onRetry={() => void refetch()} />
          </div>
        ) : null}
        {toggle.error ? (
          <div className="p-4">
            <ErrorBanner error={toggle.error} />
          </div>
        ) : null}

        {isLoading ? (
          <Spinner />
        ) : data?.data.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-left">
              <thead>
                <tr className="border-b border-[var(--color-border-subtle)] font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--color-text-faint)]">
                  <th className="py-2.5 pl-5 pr-3 font-normal">Service</th>
                  <th className="px-3 font-normal">Status</th>
                  <th className="px-3 font-normal">Last seen</th>
                  <th className="px-3 text-right font-normal">Logs 24h</th>
                  <th className="px-3 text-right font-normal">Errors 24h</th>
                  <th className="px-3 text-right font-normal">Audit 24h</th>
                  <th className="w-[132px] px-3" />
                </tr>
              </thead>
              <tbody>
                {data.data.map((s) => (
                  <tr key={s.id} className={cn('border-b border-[var(--color-border-subtle)] last:border-0', !s.is_active && 'opacity-60')}>
                    <td className="py-3 pl-5 pr-3">
                      <div className="flex items-center gap-2">
                        <Link to={`/logs?service=${encodeURIComponent(s.id)}`} className="font-mono text-[13px] hover:text-[var(--color-accent-text)]">
                          {s.id}
                        </Link>
                        {s.is_protected && (
                          <span title="System service — cannot be disabled">
                            <ShieldCheck className="size-3.5 text-[var(--color-text-faint)]" />
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-[var(--color-text-muted)]">{s.name}</div>
                      {s.description && (
                        <div className="mt-0.5 max-w-md truncate text-xs text-[var(--color-text-faint)]">{s.description}</div>
                      )}
                    </td>
                    <td className="px-3">
                      <span
                        className="inline-flex h-5 items-center gap-1.5 rounded-full border px-2 font-mono text-[10.5px]"
                        style={
                          s.is_active
                            ? { color: 'var(--color-success)', borderColor: 'var(--color-success-border)', background: 'var(--color-success-soft)' }
                            : { color: 'var(--color-text-faint)', borderColor: 'var(--color-border)' }
                        }
                      >
                        <span className="size-1.5 rounded-full" style={{ background: s.is_active ? 'var(--color-success)' : 'var(--color-text-faint)' }} />
                        {s.is_active ? 'active' : 'disabled'}
                      </span>
                    </td>
                    <td className="px-3 font-mono text-xs text-[var(--color-text-muted)]">
                      {relativeTime(s.activity?.last_seen_at)}
                    </td>
                    <td className="tabular px-3 text-right font-mono text-[13px]">{integer(s.activity?.app_logs_24h ?? 0)}</td>
                    <td
                      className="tabular px-3 text-right font-mono text-[13px]"
                      style={{ color: s.activity?.errors_24h ? 'var(--color-danger)' : 'var(--color-text-faint)' }}
                    >
                      {integer(s.activity?.errors_24h ?? 0)}
                    </td>
                    <td className="tabular px-3 text-right font-mono text-[13px]">{integer(s.activity?.audit_logs_24h ?? 0)}</td>
                    <td className="px-3">
                      <div className="flex justify-end gap-0.5">
                        <IconButton label="Integration snippet" onClick={() => setIntegrating(s)}>
                          <Code2 className="size-4" />
                        </IconButton>
                        <IconButton label="Edit" onClick={() => setEditing(s)}>
                          <Pencil className="size-3.5" />
                        </IconButton>
                        <IconButton
                          label={s.is_active ? 'Disable' : 'Enable'}
                          disabled={s.is_protected && s.is_active}
                          className="disabled:cursor-not-allowed disabled:opacity-30"
                          onClick={() => (s.is_active ? setConfirming(s) : toggle.mutate(s))}
                        >
                          <Power className={cn('size-3.5', s.is_active ? '' : 'text-[var(--color-success)]')} />
                        </IconButton>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            title={q || status !== 'all' ? 'No services match' : 'No services yet'}
            hint="A service must be registered before it can send logs."
            action={
              <Button variant="primary" icon={<Plus className="size-4" />} onClick={() => setEditing('new')}>
                Register service
              </Button>
            }
          />
        )}
      </Panel>

      <ServiceDialog
        key={editing === 'new' ? 'new' : editing?.id ?? 'closed'}
        service={editing}
        onClose={() => setEditing(null)}
        onSaved={(s, created) => {
          setEditing(null)
          void queryClient.invalidateQueries({ queryKey: ['services'] })
          if (created) setIntegrating(s)
        }}
      />

      <Dialog
        open={!!confirming}
        onClose={() => setConfirming(null)}
        title={`Disable ${confirming?.id}?`}
        description="The service will be rejected (HTTP 403 SERVICE_DISABLED) on its next ingest. Existing logs are kept."
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirming(null)}>
              Cancel
            </Button>
            <Button variant="danger" loading={toggle.isPending} onClick={() => confirming && toggle.mutate(confirming)}>
              Disable
            </Button>
          </>
        }
      >
        <p className="text-sm text-[var(--color-text-muted)]">You can enable it again at any time.</p>
      </Dialog>

      <IntegrationDialog service={integrating} onClose={() => setIntegrating(null)} />
    </>
  )
}

function ServiceDialog({
  service,
  onClose,
  onSaved,
}: {
  service: Service | 'new' | null
  onClose: () => void
  onSaved: (s: Service, created: boolean) => void
}) {
  const isNew = service === 'new'
  const existing = service && service !== 'new' ? service : null
  const [id, setId] = useState('')
  const [name, setName] = useState(existing?.name ?? '')
  const [description, setDescription] = useState(existing?.description ?? '')

  const save = useMutation({
    mutationFn: () =>
      isNew
        ? api.createService({ id, name, description: description || undefined })
        : api.updateService(existing!.id, { name, description: description || null }),
    onSuccess: (s) => onSaved(s, isNew),
  })

  const fieldErrors = save.error instanceof ApiError ? save.error.fieldErrors : {}
  const fieldError = (name: string) => fieldErrors[`body.${name}`]?.join(', ')

  return (
    <Dialog
      open={!!service}
      onClose={onClose}
      title={isNew ? 'Register service' : `Edit ${existing?.id}`}
      description={isNew ? 'Producers send this id as source_service.' : undefined}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" loading={save.isPending} disabled={!name.trim() || (isNew && !id.trim())} onClick={() => save.mutate()}>
            {isNew ? 'Register' : 'Save'}
          </Button>
        </>
      }
    >
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          save.mutate()
        }}
      >
        {isNew && (
          <Field label="Service id" hint="Lowercase letters, digits, '.', '_' or '-'. Cannot be changed later." error={fieldError('id')}>
            <Input
              autoFocus
              value={id}
              onChange={(e) => setId(e.target.value.toLowerCase())}
              placeholder="billing-api"
              className="font-mono"
              maxLength={64}
            />
          </Field>
        )}
        <Field label="Display name" error={fieldError('name')}>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Billing API" maxLength={128} autoFocus={!isNew} />
        </Field>
        <Field label="Description" error={fieldError('description')}>
          <Textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What this service does" maxLength={2000} />
        </Field>
        {save.error && !Object.keys(fieldErrors).length ? <ErrorBanner error={save.error} /> : null}
        <button type="submit" hidden />
      </form>
    </Dialog>
  )
}

function IntegrationDialog({ service, onClose }: { service: Service | null; onClose: () => void }) {
  const [lang, setLang] = useState<'js' | 'py' | 'env'>('js')
  const origin = window.location.origin
  const id = service?.id ?? 'my-service'
  const snippets = {
    env: `LMS_URL=${origin}\nLMS_INGEST_SECRET=<INGEST_SIGNING_SECRET from the LMS .env>\nLMS_SOURCE_SERVICE=${id}`,
    js: `// npm install github:Sanjaa46/voicollo_log_client_js#v1.0.0
import { LMSClient } from 'lms-logger'

const lms = new LMSClient({
  baseUrl: process.env.LMS_URL,            // ${origin}
  secret: process.env.LMS_INGEST_SECRET,
  sourceService: '${id}',
  environment: process.env.NODE_ENV ?? 'production',
  buffered: true,                          // batch in the background, never throw
})

lms.info('Service started', { version: '1.4.2' })
lms.error('Payment failed', { orderId: 8812 }, { traceId: req.id })
await lms.audit({
  actorId: user.id, actorType: 'USER',
  action: 'RECORD_DELETE', targetResource: '/records/42', outcome: 'SUCCESS',
})

process.on('SIGTERM', () => lms.close())  // flushes the buffer`,
    py: `# pip install "lms-logger @ git+https://github.com/Sanjaa46/voicollo_log_client_py@v1.0.0"
import os
from lms_logger import LMSClient

lms = LMSClient(
    base_url=os.environ["LMS_URL"],          # ${origin}
    secret=os.environ["LMS_INGEST_SECRET"],
    source_service="${id}",
    environment="production",
)

lms.info("Service started", context={"version": "1.4.2"})
lms.error("Payment failed", context={"order_id": 8812}, trace_id=request_id)
lms.audit(
    actor_id=user.id, actor_type="USER",
    action="RECORD_DELETE", target_resource="/records/42", outcome="SUCCESS",
)

# or route stdlib logging:  logging.getLogger().addHandler(lms.handler())`,
  }
  return (
    <Dialog wide open={!!service} onClose={onClose} title={`Send logs from ${id}`} description="Requests are signed with HMAC-SHA256 using the shared ingest secret.">
      <div className="mb-3 flex items-center justify-between">
        <Segmented
          label="Language"
          value={lang}
          onChange={setLang}
          options={[
            { value: 'js', label: 'Node.js' },
            { value: 'py', label: 'Python' },
            { value: 'env', label: '.env' },
          ]}
        />
        <CopyButton value={snippets[lang]} label="Copy snippet" />
      </div>
      <pre className="max-h-[380px] overflow-auto rounded-[var(--radius-md)] border border-[var(--color-border-subtle)] bg-[var(--color-bg)] p-3.5 font-mono text-[12px] leading-relaxed text-[var(--color-text-muted)]">
        {snippets[lang]}
      </pre>
    </Dialog>
  )
}
