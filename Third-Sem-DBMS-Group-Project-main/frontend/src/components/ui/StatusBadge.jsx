import { STATUS_TONES } from '../../utils/status.js'

const TONE_CLASSES = {
  ok: 'border-ok/30 bg-ok/10 text-ok',
  warn: 'border-warn/30 bg-warn/10 text-warn',
  danger: 'border-danger/30 bg-danger/10 text-danger',
  accent: 'border-accent/30 bg-accent/10 text-accent',
  muted: 'border-line bg-panel-2 text-muted',
  neutral: 'border-line bg-panel-2 text-ink/80',
}

const DOT_CLASSES = {
  ok: 'bg-ok',
  warn: 'bg-warn',
  danger: 'bg-danger',
  accent: 'bg-accent',
  muted: 'bg-faint',
  neutral: 'bg-muted',
}

export function Badge({ tone = 'neutral', dot = false, children }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded border px-1.5 py-0.5 text-[11px] font-medium leading-4 ${TONE_CLASSES[tone]}`}
    >
      {dot && <span className={`size-1.5 rounded-full ${DOT_CLASSES[tone]}`} aria-hidden="true" />}
      {children}
    </span>
  )
}

export function StatusBadge({ status }) {
  const config = STATUS_TONES[status] ?? { tone: 'neutral', label: status }
  return (
    <Badge tone={config.tone} dot>
      {config.label}
    </Badge>
  )
}
