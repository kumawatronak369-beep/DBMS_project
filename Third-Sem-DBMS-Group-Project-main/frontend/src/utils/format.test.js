import { describe, expect, it } from 'vitest'
import {
  destinationLabel,
  formatBucket,
  formatDate,
  formatDateTime,
  formatNumber,
  formatPort,
  formatTime,
  relativeTime,
} from './format.js'
import { STATUS_TONES, titleCase } from './status.js'

describe('formatPort', () => {
  it('prints a port as a plain identifier', () => {
    expect(formatPort(443)).toBe('443')
    expect(formatPort(56188)).toBe('56188')
    expect(formatPort(65535)).toBe('65535')
  })

  it('shows a dash for anything that is not an integer', () => {
    for (const value of [null, undefined, '', '443', NaN, 1.5, Infinity]) expect(formatPort(value)).toBe('—')
  })
})

describe('formatNumber', () => {
  it('groups thousands', () => {
    expect(formatNumber(1234567)).toBe('1,234,567')
    expect(formatNumber(0)).toBe('0')
  })
  it('shows a dash for anything that is not a number', () => {
    expect(formatNumber(undefined)).toBe('—')
    expect(formatNumber(null)).toBe('—')
    expect(formatNumber('12')).toBe('—')
  })
})

describe('date formatting', () => {
  it('formats a full timestamp', () => {
    expect(formatDateTime('2026-09-19T20:15:32')).toMatch(/^19 Sep(t)? 2026, 20:15:32$/)
  })
  it('formats date-only and time-only', () => {
    expect(formatDate('2026-09-19T20:15:32')).toMatch(/^19 Sep(t)? 2026$/)
    expect(formatTime('2026-09-19T20:15:32')).toBe('20:15:32')
  })
  it.each([null, undefined, '', 'not a date'])('shows a dash for %j', (value) => {
    expect(formatDateTime(value)).toBe('—')
    expect(formatDate(value)).toBe('—')
    expect(formatTime(value)).toBe('—')
  })
  it('labels chart buckets by hour or by day', () => {
    expect(formatBucket('2026-09-19T07:00:00', 'hour')).toBe('07:00')
    expect(formatBucket('2026-09-19T07:00:00', 'day')).toMatch(/^19 Sep(t)?$/)
    expect(formatBucket('nonsense', 'hour')).toBe('')
  })
})

describe('relativeTime', () => {
  const now = new Date('2026-09-20T12:00:00').getTime()
  const pad = (n) => String(n).padStart(2, '0')
  const stamp = (secondsFromNow) => {
    const d = new Date(now + secondsFromNow * 1000)
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  }

  it('describes the past', () => {
    expect(relativeTime(stamp(-2), now)).toBe('just now')
    expect(relativeTime(stamp(-30), now)).toBe('30s ago')
    expect(relativeTime(stamp(-5 * 60), now)).toBe('5m ago')
    expect(relativeTime(stamp(-3 * 3600), now)).toBe('3h ago')
    expect(relativeTime(stamp(-3 * 86400), now)).toBe('3d ago')
  })
  it('describes the future (for example when a session ends)', () => {
    expect(relativeTime(stamp(57 * 60), now)).toBe('in 57m')
    expect(relativeTime(stamp(2 * 3600), now)).toBe('in 2h')
  })
  it('falls back to a plain date for old timestamps and "never" for missing ones', () => {
    expect(relativeTime('2026-01-01T00:00:00', now)).toMatch(/^01 Jan 2026$/)
    expect(relativeTime(null, now)).toBe('never')
    expect(relativeTime('garbage', now)).toBe('never')
  })
})

describe('destinationLabel', () => {
  it('uses the domain, and never invents one when there is none', () => {
    expect(destinationLabel('github.com', '203.0.113.20')).toBe('github.com')
    expect(destinationLabel(null, '192.0.2.77')).toBe('192.0.2.77')
  })
})

describe('status helpers', () => {
  it('title-cases enum values', () => {
    expect(titleCase('DEVELOPMENT')).toBe('Development')
    expect(titleCase('')).toBe('')
    expect(titleCase(undefined)).toBe('')
  })
  it('gives every status a tone and label (green only for healthy)', () => {
    expect(STATUS_TONES.ACTIVE).toEqual({ tone: 'ok', label: 'Active' })
    expect(STATUS_TONES.OFFLINE.tone).toBe('muted')
    expect(STATUS_TONES.INACTIVE.tone).toBe('muted')
    expect(STATUS_TONES.DISABLED.tone).toBe('muted')
    expect(STATUS_TONES.ADMIN.tone).toBe('accent')
  })
})
