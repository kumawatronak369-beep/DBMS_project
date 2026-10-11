import { ChevronLeft, ChevronRight } from 'lucide-react'
import { formatNumber } from '../../utils/format.js'
import { Button } from './Button.jsx'

export function Pagination({ data, onPageChange }) {
  const { total, page, page_size: pageSize } = data
  const pages = Math.max(1, Math.ceil(total / pageSize))
  const first = total === 0 ? 0 : (page - 1) * pageSize + 1
  const last = Math.min(total, page * pageSize)

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line px-4 py-2.5 text-xs text-muted">
      <span>
        {total === 0 ? 'No results' : `${formatNumber(first)}–${formatNumber(last)} of ${formatNumber(total)}`}
      </span>
      <div className="flex items-center gap-2">
        <span className="tabular-nums">
          Page {page} of {pages}
        </span>
        <Button size="sm" icon={ChevronLeft} disabled={page <= 1} onClick={() => onPageChange(page - 1)} aria-label="Previous page">
          Prev
        </Button>
        <Button
          size="sm"
          disabled={page >= pages}
          onClick={() => onPageChange(page + 1)}
          aria-label="Next page"
          className="flex-row-reverse"
          icon={ChevronRight}
        >
          Next
        </Button>
      </div>
    </div>
  )
}
