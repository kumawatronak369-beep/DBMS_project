import { AlertTriangle, Compass, Inbox, RefreshCw, ShieldAlert, WifiOff } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from './Button.jsx'

export function Skeleton({ className = '', style }) {
  return <div className={`nm-skeleton rounded ${className}`} style={style} aria-hidden="true" />
}

export function SkeletonRows({ rows = 5, className = '' }) {
  return (
    <div className={`space-y-2 p-4 ${className}`} role="status" aria-label="Loading">
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} className="h-7 w-full" />
      ))}
    </div>
  )
}

export function SkeletonBlock({ height = 240 }) {
  return (
    <div className="p-4" role="status" aria-label="Loading">
      <Skeleton className="w-full" style={{ height }} />
    </div>
  )
}

export function EmptyState({ title = 'Nothing to show', hint, icon: Icon = Inbox, action }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1 px-4 py-10 text-center">
      <Icon size={22} className="mb-1 text-faint" aria-hidden="true" />
      <p className="text-sm font-medium text-ink">{title}</p>
      {hint && <p className="max-w-sm text-xs text-muted">{hint}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  )
}

function describeError(error) {
  if (error?.status === 404) return { icon: Compass, title: 'Not found', retryable: false }
  if (error?.isNetworkError) return { icon: WifiOff, title: "Can't reach the server" }
  if (error?.status === 403) return { icon: ShieldAlert, title: 'Not permitted' }
  return { icon: AlertTriangle, title: 'Unable to load this data' }
}

export function ErrorState({ error, onRetry, title, backTo }) {
  const described = describeError(error)
  const Icon = described.icon
  const notFound = described.retryable === false
  return (
    <div className="flex flex-col items-center justify-center gap-1 px-4 py-10 text-center" role="alert">
      <Icon size={22} className={`mb-1 ${notFound ? 'text-muted' : 'text-danger'}`} aria-hidden="true" />
      <p className="text-sm font-medium text-ink">{notFound ? described.title : (title ?? described.title)}</p>
      <p className="max-w-md text-xs text-muted">{error?.message ?? 'Something went wrong. Please try again.'}</p>
      <div className="mt-3 flex items-center gap-2">
        {onRetry && !notFound && (
          <Button size="sm" icon={RefreshCw} onClick={onRetry}>
            Try again
          </Button>
        )}
        {backTo && (
          <Link to={backTo.to}>
            <Button size="sm">{backTo.label}</Button>
          </Link>
        )}
      </div>
    </div>
  )
}

export function DataState({ result, isEmpty, empty, skeleton, errorTitle, backTo, quiet = false, children }) {
  const { data, error, loading, reload } = result

  if (data === null) {
    if (error) return <ErrorState error={error} onRetry={reload} title={errorTitle} backTo={backTo} />
    return skeleton ?? <SkeletonRows />
  }
  if (isEmpty?.(data)) {
    return (
      <>
        {error && !quiet && <StaleNotice error={error} onRetry={reload} />}
        <EmptyState {...empty} />
      </>
    )
  }
  return (
    <div className={loading ? 'opacity-70 transition-opacity' : 'transition-opacity'}>
      {error && !quiet && <StaleNotice error={error} onRetry={reload} />}
      {children(data)}
    </div>
  )
}

function StaleNotice({ error, onRetry }) {
  return (
    <div className="flex items-center justify-between gap-2 border-b border-warn/30 bg-warn/10 px-4 py-2 text-xs text-warn">
      <span>Could not refresh: {error.message}</span>
      <button type="button" onClick={onRetry} className="font-medium underline underline-offset-2">
        Retry
      </button>
    </div>
  )
}
