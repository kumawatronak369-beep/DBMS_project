import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ChartTooltip } from './ChartTooltip.jsx'

// jsdom cannot lay anything out, so report a real size
globalThis.ResizeObserver = class {
  constructor(callback) {
    this.callback = callback
  }
  observe(target) {
    this.callback([{ target, contentRect: { width: 640, height: 240 } }], this)
  }
  unobserve() {}
  disconnect() {}
}

const { ActivityChart } = await vi.importActual('./ActivityChart.jsx')
const { NodeActivityChart, TopDestinationsChart } = await vi.importActual('./BarCharts.jsx')

const points = [
  { bucket: '2026-09-20T07:00:00', event_count: 3 },
  { bucket: '2026-09-20T08:00:00', event_count: 9 },
]

describe('ActivityChart', () => {
  it('mounts with an accessible label and the requested height', () => {
    render(<ActivityChart points={points} bucket="hour" height={260} />)
    const chart = screen.getByRole('img', { name: 'Network activity over time' })
    expect(chart).toHaveStyle({ height: '260px' })
  })

  it('accepts empty data and daily buckets without failing', () => {
    render(<ActivityChart points={[]} bucket="day" />)
    expect(screen.getByRole('img', { name: 'Network activity over time' })).toBeInTheDocument()
  })
})

describe('bar charts', () => {
  it('TopDestinationsChart is labelled, and copes with a destination that has no domain', () => {
    const rows = [
      { destination_id: 1, domain: 'google.com', ip_address: '198.51.100.10', event_count: 10, unique_devices: 5 },
      { destination_id: 2, domain: null, ip_address: '192.0.2.77', event_count: 2, unique_devices: 1 },
    ]
    render(<TopDestinationsChart rows={rows} />)
    expect(screen.getByRole('img', { name: 'Top destinations by events' })).toBeInTheDocument()
  })

  it('sizes the destination chart to the number of rows unless told otherwise', () => {
    const rows = Array.from({ length: 6 }, (_, i) => ({ destination_id: i, domain: `d${i}.com`, ip_address: '203.0.113.1', event_count: 1, unique_devices: 1 }))
    const { rerender } = render(<TopDestinationsChart rows={rows} />)
    expect(screen.getByRole('img')).toHaveStyle({ height: '228px' })
    rerender(<TopDestinationsChart rows={rows} height={400} />)
    expect(screen.getByRole('img')).toHaveStyle({ height: '400px' })
  })

  it('NodeActivityChart is labelled and accepts an empty list', () => {
    render(<NodeActivityChart rows={[]} />)
    expect(screen.getByRole('img', { name: 'Events by node' })).toBeInTheDocument()
  })
})

describe('ChartTooltip', () => {
  const describePoint = (point) => ({ title: point.name, rows: [['Events', String(point.count)], ['Devices', String(point.devices)]] })

  it('renders nothing when inactive or empty', () => {
    const { container, rerender } = render(<ChartTooltip active={false} payload={[{ payload: {} }]} describe={describePoint} />)
    expect(container).toBeEmptyDOMElement()
    rerender(<ChartTooltip active payload={[]} describe={describePoint} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('shows a title and label/value rows for the hovered point', () => {
    render(<ChartTooltip active payload={[{ payload: { name: 'Computer Lab A', count: 249, devices: 5 } }]} describe={describePoint} />)
    expect(screen.getByText('Computer Lab A')).toBeInTheDocument()
    expect(screen.getByText('Events').nextSibling).toHaveTextContent('249')
    expect(screen.getByText('Devices').nextSibling).toHaveTextContent('5')
  })
})
