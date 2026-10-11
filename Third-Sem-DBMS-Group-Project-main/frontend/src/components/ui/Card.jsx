export function Card({ className = '', children, ...props }) {
  return (
    <section className={`min-w-0 rounded-lg border border-line bg-panel ${className}`} {...props}>
      {children}
    </section>
  )
}

export function CardHeader({ title, subtitle, icon: Icon, actions }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3">
      <div className="flex min-w-0 items-center gap-2">
        {Icon && <Icon size={15} className="shrink-0 text-muted" aria-hidden="true" />}
        <div className="min-w-0">
          <h2 className="truncate text-sm font-medium text-ink">{title}</h2>
          {subtitle && <p className="truncate text-xs text-muted">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}

export function CardBody({ className = '', children }) {
  return <div className={`p-4 ${className}`}>{children}</div>
}
