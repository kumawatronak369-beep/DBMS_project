
export function TableWrap({ children }) {
  return <div className="overflow-x-auto">{children}</div>
}

export function Table({ children, className = '' }) {
  return <table className={`w-full border-collapse text-left text-[13px] ${className}`}>{children}</table>
}

export function Th({ children, className = '', align = 'left' }) {
  return (
    <th
      scope="col"
      className={`whitespace-nowrap border-b border-line px-4 py-2 text-[11px] font-medium uppercase tracking-wider text-muted ${
        align === 'right' ? 'text-right' : 'text-left'
      } ${className}`}
    >
      {children}
    </th>
  )
}

export function Tr({ onClick, children, className = '', ...props }) {
  return (
    <tr
      onClick={onClick}
      onKeyDown={
        onClick
          ? (event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault()
                onClick(event)
              }
            }
          : undefined
      }
      tabIndex={onClick ? 0 : undefined}
      className={`border-b border-line/60 last:border-0 ${
        onClick ? 'cursor-pointer transition-colors hover:bg-panel-2 focus-visible:bg-panel-2' : ''
      } ${className}`}
      {...props}
    >
      {children}
    </tr>
  )
}

export function Td({ children, className = '', align = 'left', mono = false, ...props }) {
  return (
    <td
      className={`px-4 py-2 align-middle ${align === 'right' ? 'text-right tabular-nums' : ''} ${
        mono ? 'font-mono text-xs text-ink/90' : ''
      } ${className}`}
      {...props}
    >
      {children}
    </td>
  )
}
