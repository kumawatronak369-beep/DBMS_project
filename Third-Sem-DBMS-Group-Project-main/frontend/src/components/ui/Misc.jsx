import { Link } from 'react-router-dom'
import { usePageTitle } from '../../hooks/usePageTitle.js'
import { Skeleton } from './States.jsx'

export function KpiCard({ label, value, icon: Icon, hint, loading = false, to }) {
  const body = (
    <div className="flex items-start justify-between gap-3 rounded-lg border border-line bg-panel px-4 py-3 transition-colors hover:border-line-strong">
      <div className="min-w-0">
        <p className="text-[11px] font-medium uppercase tracking-wider text-muted">{label}</p>
        {loading ? (
          <Skeleton className="mt-2 h-7 w-20" />
        ) : (
          <p className="mt-1 text-2xl font-semibold tabular-nums text-ink">{value}</p>
        )}
        {hint && !loading && <p className="mt-0.5 text-xs text-muted">{hint}</p>}
      </div>
      {Icon && (
        <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-accent/10 text-accent">
          <Icon size={16} aria-hidden="true" />
        </span>
      )}
    </div>
  )
  return to ? (
    <Link to={to} className="block">
      {body}
    </Link>
  ) : (
    body
  )
}

export function DetailList({ items }) {
  return (
    <dl className="grid grid-cols-[8.5rem_minmax(0,1fr)] gap-x-4 gap-y-2.5 text-[13px]">
      {items.map(({ label, value, mono }) => (
        <div key={label} className="contents">
          <dt className="text-muted">{label}</dt>
          <dd className={`min-w-0 break-words text-ink ${mono ? 'font-mono text-xs' : ''}`}>{value ?? '—'}</dd>
        </div>
      ))}
    </dl>
  )
}

export function PageHeader({ title, subtitle, actions, breadcrumb }) {
  usePageTitle(title)

  return (
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        {breadcrumb && <div className="mb-1 text-xs text-muted">{breadcrumb}</div>}
        <h1 className="truncate text-lg font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

const RANGES = [
  { value: '24h', label: '24 hours' },
  { value: '7d', label: '7 days' },
  { value: '30d', label: '30 days' },
]

export function RangeSelect({ value, onChange, options = RANGES }) {
  return (
    <div className="inline-flex rounded-md border border-line-strong bg-surface p-0.5" role="group" aria-label="Time range">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          aria-pressed={value === option.value}
          className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
            value === option.value ? 'bg-accent-strong text-white' : 'text-muted hover:text-ink'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

export function Mono({ children, className = '' }) {
  return <span className={`font-mono text-xs text-ink/90 ${className}`}>{children}</span>
}

export function DestinationName({ domain, ip }) {
  return domain ? (
    <span className="text-ink">{domain}</span>
  ) : (
    <span className="text-muted" title="No DNS name was observed for this destination">
      {ip} <span className="text-[11px] text-faint">(unresolved)</span>
    </span>
  )
}
