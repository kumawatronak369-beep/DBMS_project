// the API sends naive local timestamps; new Date reads them as local time

const dateTimeFormat = new Intl.DateTimeFormat('en-GB', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
})
const dateFormat = new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
const timeFormat = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
const shortDayFormat = new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short' })
const hourFormat = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false })
const numberFormat = new Intl.NumberFormat('en-US')

function toDate(value) {
  if (!value) return null
  const date = value instanceof Date ? value : new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

export const formatDateTime = (value) => (toDate(value) ? dateTimeFormat.format(toDate(value)) : '—')
export const formatDate = (value) => (toDate(value) ? dateFormat.format(toDate(value)) : '—')
export const formatTime = (value) => (toDate(value) ? timeFormat.format(toDate(value)) : '—')
export const formatNumber = (value) => (typeof value === 'number' ? numberFormat.format(value) : '—')
// ports are identifiers, so no thousands separators
export const formatPort = (value) => (Number.isInteger(value) ? String(value) : '—')

export function formatBucket(value, bucket) {
  const date = toDate(value)
  if (!date) return ''
  return bucket === 'hour' ? hourFormat.format(date) : shortDayFormat.format(date)
}

export function relativeTime(value, now = Date.now()) {
  const date = toDate(value)
  if (!date) return 'never'
  const signed = Math.round((now - date.getTime()) / 1000)
  const future = signed < 0
  const seconds = Math.abs(signed)
  const phrase = (amount, unit) => (future ? `in ${amount}${unit}` : `${amount}${unit} ago`)

  if (seconds < 5) return 'just now'
  if (seconds < 60) return phrase(seconds, 's')
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return phrase(minutes, 'm')
  const hours = Math.round(minutes / 60)
  if (hours < 48) return phrase(hours, 'h')
  const days = Math.round(hours / 24)
  if (days < 60) return phrase(days, 'd')
  return formatDate(date)
}

export const destinationLabel = (domain, ip) => domain || ip
