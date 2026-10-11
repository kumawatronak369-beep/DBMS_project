import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { reply } from '../test/fetchMock.js'
import { activity, node, nodeActivity, paginated, topDestination, topDevice } from '../test/fixtures.js'
import { renderApp } from '../test/render.jsx'

const routes = (over = {}) => ({
  'GET /api/nodes': paginated([node(), node({ node_id: 2, node_name: 'Computer Lab B' })]),
  'GET /api/reports/activity-over-time': activity(),
  'GET /api/reports/top-destinations': [
    topDestination(),
    topDestination({ destination_id: 7, domain: null, ip_address: '192.0.2.77', category: 'UNKNOWN', event_count: 3, unique_devices: 1 }),
  ],
  'GET /api/reports/top-devices': [topDevice()],
  'GET /api/reports/activity-by-node': [nodeActivity()],
  ...over,
})
const renderReports = (over = {}) => renderApp('/reports', { routes: routes(over) })
const card = (title) => screen.getByRole('heading', { name: title }).closest('section')
const loaded = () => screen.findByTestId('activity-chart')
const setDate = (input, value) => {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, value)
  input.dispatchEvent(new Event('input', { bubbles: true }))
}

describe('ReportsPage', () => {
  it('renders every report from backend data for the default 7-day range', async () => {
    const { api } = renderReports()
    await loaded()
    expect(screen.getByRole('button', { name: 'Last 7 days' })).toHaveAttribute('aria-pressed', 'true')
    for (const name of ['top-destinations', 'top-devices', 'activity-by-node', 'activity-over-time']) {
      expect(api.lastCall(`GET /api/reports/${name}`).query.range).toBe('7d')
    }

    const destinations = card('Most visited destinations')
    expect(await within(destinations).findByRole('link', { name: 'google.com' })).toHaveAttribute('href', '/destinations/6')
    expect(within(destinations).getByText('144')).toBeInTheDocument()
    expect(within(destinations).getByText('(unresolved)')).toBeInTheDocument()
    expect(within(destinations).getByTestId('top-destinations-chart')).toBeInTheDocument()

    const devices = card('Most active devices')
    expect(await within(devices).findByRole('link', { name: 'PC-LAB-A-001' })).toHaveAttribute('href', '/devices/1')
    expect(within(devices).getByText('54')).toBeInTheDocument()

    const nodes = card('Node activity')
    expect(await within(nodes).findByRole('link', { name: 'Computer Lab A' })).toHaveAttribute('href', '/nodes/1')
    expect(within(nodes).getByText('249')).toBeInTheDocument()
  })

  it('re-queries every report when the range changes', async () => {
    const { api } = renderReports()
    await loaded()
    await userEvent.click(screen.getByRole('button', { name: 'Last 24 hours' }))
    await waitFor(() => expect(api.lastCall('GET /api/reports/top-devices').query.range).toBe('24h'))
    expect(api.lastCall('GET /api/reports/activity-by-node').query.range).toBe('24h')
    await userEvent.click(screen.getByRole('button', { name: 'Last 30 days' }))
    await waitFor(() => expect(api.lastCall('GET /api/reports/top-destinations').query.range).toBe('30d'))
  })

  it('filters only the activity chart by node', async () => {
    const { api } = renderReports()
    await loaded()
    const others = api.callsTo('GET /api/reports/top-devices').length
    await waitFor(() => expect(within(screen.getByLabelText('Filter by node')).getByRole('option', { name: 'Computer Lab B' })).toBeInTheDocument())
    await userEvent.selectOptions(screen.getByLabelText('Filter by node'), 'Computer Lab B')
    await waitFor(() => expect(api.lastCall('GET /api/reports/activity-over-time').query.nodeId).toBe('2'))
    expect(api.callsTo('GET /api/reports/top-devices')).toHaveLength(others)
  })

  it('does not query in custom mode until both dates are valid', async () => {
    const { api } = renderReports()
    await loaded()
    await userEvent.click(screen.getByRole('button', { name: 'Custom range' }))
    expect(screen.getByText('Choose a date range')).toBeInTheDocument()
    expect(screen.getByText('Pick both dates to run the reports.')).toBeInTheDocument()
    const before = api.callsTo('GET /api/reports/top-devices').length

    setDate(screen.getByLabelText('From date'), '2026-09-19')
    expect(api.callsTo('GET /api/reports/top-devices')).toHaveLength(before)

    setDate(screen.getByLabelText('To date'), '2026-09-01')
    expect(await screen.findByText('Start date is after the end date')).toBeInTheDocument()
    expect(api.callsTo('GET /api/reports/top-devices')).toHaveLength(before)

    setDate(screen.getByLabelText('To date'), '2026-09-20')
    await waitFor(() =>
      expect(api.lastCall('GET /api/reports/top-devices').query).toEqual({ startDate: '2026-09-19', endDate: '2026-09-20', limit: '10' }),
    )
  })

  it('shows empty states when the period has no data', async () => {
    renderReports({
      'GET /api/reports/activity-over-time': activity({ points: [{ bucket: '2026-09-20T07:00:00', event_count: 0 }] }),
      'GET /api/reports/top-destinations': [],
      'GET /api/reports/top-devices': [],
      'GET /api/reports/activity-by-node': [],
    })
    expect(await screen.findByText('No activity in this period')).toBeInTheDocument()
    expect(await screen.findByText('No destinations in this period')).toBeInTheDocument()
    expect(await screen.findByText('No device activity in this period')).toBeInTheDocument()
    expect(await screen.findByText('No nodes registered')).toBeInTheDocument()
  })

  it('shows an error in one report without hiding the others', async () => {
    renderReports({ 'GET /api/reports/top-devices': reply(500, { detail: 'Internal server error' }) })
    await loaded()
    expect(await within(card('Most active devices')).findByText('Unable to load this data')).toBeInTheDocument()
    expect(await within(card('Node activity')).findByRole('link', { name: 'Computer Lab A' })).toBeInTheDocument()
  })
})
