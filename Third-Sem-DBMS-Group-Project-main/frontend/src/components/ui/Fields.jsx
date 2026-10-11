import { Search } from 'lucide-react'
import { useId } from 'react'

const CONTROL =
  'h-8 rounded-md border border-line-strong bg-surface px-2.5 text-sm text-ink placeholder:text-faint transition-colors hover:border-faint focus:border-accent focus:outline-none disabled:opacity-50'

export function Field({ label, error, hint, children, className = '' }) {
  const id = useId()
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1 block text-xs font-medium text-muted">
        {label}
      </label>
      {typeof children === 'function' ? children(id) : children}
      {error ? (
        <p className="mt-1 text-xs text-danger" role="alert">
          {error}
        </p>
      ) : (
        hint && <p className="mt-1 text-xs text-faint">{hint}</p>
      )}
    </div>
  )
}

const widthOf = (className) => (/(^|\s)w-/.test(className) ? '' : 'w-full')

export function TextInput({ className = '', ...props }) {
  return <input className={`${CONTROL} ${widthOf(className)} ${className}`} {...props} />
}

export function Select({ className = '', children, ...props }) {
  return (
    <select className={`${CONTROL} ${widthOf(className)} pr-7 ${className}`} {...props}>
      {children}
    </select>
  )
}

export function SearchInput({ value, onChange, placeholder = 'Search…', label = 'Search', className = '' }) {
  return (
    <div className={`relative ${className}`}>
      <Search size={14} className="pointer-events-none absolute left-2.5 top-2.5 text-faint" aria-hidden="true" />
      <input
        type="search"
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className={`${CONTROL} w-full pl-8`}
      />
    </div>
  )
}
