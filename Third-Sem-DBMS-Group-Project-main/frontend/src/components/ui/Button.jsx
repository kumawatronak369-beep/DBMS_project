import { Loader2 } from 'lucide-react'

const VARIANTS = {
  primary: 'border-accent-strong bg-accent-strong text-white hover:bg-accent hover:border-accent',
  secondary: 'border-line-strong bg-panel-2 text-ink hover:bg-line',
  ghost: 'border-transparent text-muted hover:bg-panel-2 hover:text-ink',
  danger: 'border-danger/40 bg-danger/10 text-danger hover:bg-danger/20',
}

const SIZES = {
  sm: 'h-7 px-2.5 text-xs gap-1.5',
  md: 'h-8 px-3 text-sm gap-2',
}

export function Button({
  variant = 'secondary',
  size = 'md',
  icon: Icon,
  loading = false,
  disabled = false,
  className = '',
  children,
  type = 'button',
  ...props
}) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      className={`inline-flex shrink-0 items-center justify-center rounded-md border font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...props}
    >
      {loading ? (
        <Loader2 size={14} className="animate-spin" aria-hidden="true" />
      ) : (
        Icon && <Icon size={14} aria-hidden="true" />
      )}
      {children}
    </button>
  )
}

export function IconButton({ icon: Icon, label, className = '', ...props }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={`inline-flex size-8 items-center justify-center rounded-md text-muted transition-colors hover:bg-panel-2 hover:text-ink disabled:opacity-50 ${className}`}
      {...props}
    >
      <Icon size={16} aria-hidden="true" />
    </button>
  )
}
