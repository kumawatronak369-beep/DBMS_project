import { CheckCircle2, Database, Loader2, Server, XCircle } from 'lucide-react'

function stateView(state) {
  if (state === 'loading') return { Icon: Loader2, tone: 'text-muted', label: 'Checking', spin: true }
  if (state === 'ok') return { Icon: CheckCircle2, tone: 'text-ok', label: 'Operational', spin: false }
  return { Icon: XCircle, tone: 'text-danger', label: 'Unavailable', spin: false }
}

function HealthRow({ icon: Icon, name, check, detail }) {
  const view = stateView(check.state)
  const StateIcon = view.Icon
  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <div className="flex min-w-0 items-center gap-2.5">
        <Icon size={15} className="shrink-0 text-muted" aria-hidden="true" />
        <div className="min-w-0">
          <p className="text-[13px] text-ink">{name}</p>
          {detail && <p className="text-xs text-muted">{detail}</p>}
        </div>
      </div>
      <span className={`inline-flex shrink-0 items-center gap-1.5 text-xs ${view.tone}`}>
        <StateIcon size={14} className={view.spin ? 'animate-spin' : ''} aria-hidden="true" />
        {view.label}
      </span>
    </div>
  )
}

export function HealthList({ health }) {
  const { api, database } = health
  const tables = database.data?.tables?.length
  const dbDetail =
    database.state === 'ok'
      ? `MySQL connected, ${tables} of 6 tables present`
      : database.data?.missing_tables?.length
        ? `Missing tables: ${database.data.missing_tables.join(', ')}`
        : database.state === 'error'
          ? 'MySQL is unreachable or the schema is missing'
          : undefined
  const apiDetail = api.state === 'error' ? (api.error?.message ?? 'The backend did not respond') : undefined

  return (
    <div className="divide-y divide-line/60">
      <HealthRow icon={Server} name="FastAPI backend" check={api} detail={apiDetail} />
      <HealthRow icon={Database} name="MySQL database" check={database} detail={dbDetail} />
    </div>
  )
}

export function HealthDots({ health }) {
  const dot = (state) => (state === 'ok' ? 'bg-ok' : state === 'loading' ? 'bg-faint' : 'bg-danger')
  const label = (name, check) => `${name}: ${stateView(check.state).label.toLowerCase()}`
  return (
    <div className="flex items-center gap-3 text-[11px] text-muted" role="status" aria-label="System health">
      <span className="inline-flex items-center gap-1.5" title={label('API', health.api)}>
        <span className={`size-1.5 rounded-full ${dot(health.api.state)}`} aria-hidden="true" />
        API
      </span>
      <span className="inline-flex items-center gap-1.5" title={label('Database', health.database)}>
        <span className={`size-1.5 rounded-full ${dot(health.database.state)}`} aria-hidden="true" />
        Database
      </span>
    </div>
  )
}
