import { Link, useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { api } from '../lib/api'
import { LogDetailBody, type FilterPatch } from '../components/LogDetail'
import { CopyButton, ErrorBanner, PageHeader, Panel, Spinner } from '../components/ui'

export function LogDetailPage() {
  const { logType, logId } = useParams()
  const navigate = useNavigate()
  const type = logType === 'audit' ? 'audit' : 'app'
  const id = Number(logId)

  const { data, error, isLoading } = useQuery({
    queryKey: ['log', type, id],
    queryFn: () => api.log(type, id),
    enabled: Number.isInteger(id) && id > 0,
  })

  const onFilter = (patch: FilterPatch) => {
    const params = new URLSearchParams(Object.entries(patch).filter(([, v]) => v) as [string, string][])
    navigate(`/logs?${params}`)
  }

  return (
    <>
      <Link to="/logs" className="mb-4 inline-flex items-center gap-1.5 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
        <ArrowLeft className="size-3.5" /> Back to explorer
      </Link>
      <PageHeader eyebrow={type === 'app' ? 'Application log' : 'Audit log'} title={`#${logId}`}>
        {data && <CopyButton value={JSON.stringify(data, null, 2)} label="Copy entry as JSON" />}
      </PageHeader>
      {isLoading && <Spinner />}
      {error ? <ErrorBanner error={error} /> : null}
      {data && (
        <Panel className="max-w-3xl p-6">
          <LogDetailBody entry={data} onFilter={onFilter} />
        </Panel>
      )}
    </>
  )
}
