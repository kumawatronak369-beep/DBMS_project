import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { reply } from '../test/fetchMock.js'
import { ANALYST, activity, historyEvent, paginated, summary } from '../test/fixtures.js'
import { dashboardRoutes, renderApp } from '../test/render.jsx'

const card = async (title) => (await screen.findByRole('heading', { name: title })).closest('section')
const kpi = (label) => screen.getByText(label).closest('a')
const loaded = async (todaysEvents = '22') => {
  const link = await screen.findByRole('link', { name: /Today's events/ })
  await within(link).findByText(todaysEvents)
  return link
}

const renderDashboard = (routes = {}, options = {}) => renderApp('/dashboard', { routes: dashboardRoutes(routes), ...options })

describe('DashboardPage: data', () => {
  it('shows skeletons while loading, then real numbers from the API', async () => {
    let release
    const held = new Promise((resolve) => (release = () => resolve(activity())))
    renderDashboard({ 'GET /api/dashboard/activity': () => held })

    const chartCard = await card('Network activity over time')
    expect(within(chartCard).getByRole('status', { name: 'Loading' })).toBeInTheDocument()
    expect(within(chartCard).queryByTestId('activity-chart')).not.toBeInTheDocument()

    release()
    expect(await within(chartCard).findByTestId('activity-chart')).toBeInTheDocument()
    await loaded()
    expect(within(kpi('Active nodes')).getByText('4')).toBeInTheDocument()
    expect(within(kpi('Registered devices')).getByText('17')).toBeInTheDocument()
    expect(within(kpi("Today's events")).getByText('22')).toBeInTheDocument()
    expect(within(kpi('Known destinations')).getByText('12')).toBeInTheDocument()
    expect(await within(kpi('Active nodes')).findByText('of 2 registered')).toBeInTheDocument()
  })

  it('links each KPI to its page', async () => {
    renderDashboard()
    await loaded()
    expect(kpi('Active nodes')).toHaveAttribute('href', '/nodes')
    expect(kpi('Registered devices')).toHaveAttribute('href', '/devices')
    expect(kpi("Today's events")).toHaveAttribute('href', '/history')
    expect(kpi('Known destinations')).toHaveAttribute('href', '/destinations')
  })

  it('passes the activity series to the chart', async () => {
    renderDashboard()
    const chart = await within(await card('Network activity over time')).findByTestId('activity-chart')
    expect(chart).toHaveAttribute('data-bucket', 'hour')
    expect(chart).toHaveAttribute('data-points', '2')
    expect(chart).toHaveAttribute('data-total', '12')
  })

  it('shows top destinations and activity by node', async () => {
    renderDashboard()
    expect(await within(await card('Top destinations')).findByTestId('top-destinations-chart')).toHaveAttribute('data-labels', 'google.com,github.com')
    expect(await within(await card('Activity by node')).findByTestId('node-activity-chart')).toHaveAttribute('data-labels', 'LAB-A,LAB-B')
  })

  it('lists the most recent events (newest first as the API returns them)', async () => {
    renderDashboard()
    const section = await card('Recent network activity')
    expect(await within(section).findAllByText('20:15:32')).toHaveLength(2)
    expect(within(section).getByText('PC-LAB-A-001')).toBeInTheDocument()
    expect(within(section).getByText('github.com')).toBeInTheDocument()
    expect(within(section).getByText('PC-LIB-002')).toBeInTheDocument()
    expect(within(section).getByText('(unresolved)')).toBeInTheDocument()
  })

  it('lists the most active devices and links to them', async () => {
    renderDashboard()
    const section = await card('Most active devices')
    expect(await within(section).findByRole('link', { name: 'PC-LAB-A-001' })).toHaveAttribute('href', '/devices/1')
    expect(within(section).getByText('54')).toBeInTheDocument()
    expect(within(section).getByText('Computer Lab B')).toBeInTheDocument()
  })

  it('shows node status and recently seen devices', async () => {
    renderDashboard()
    const nodes = await card('Node status')
    expect(await within(nodes).findByRole('link', { name: /Computer Lab A/ })).toHaveAttribute('href', '/nodes/1')
    expect(within(nodes).getByText('Active')).toBeInTheDocument()
    expect(within(nodes).getByText('Offline')).toBeInTheDocument()
    expect(within(nodes).getByText(/seen never/)).toBeInTheDocument()

    const devices = await card('Recently seen devices')
    expect(await within(devices).findByRole('link', { name: /PC-LAB-B-002/ })).toBeInTheDocument()
    expect(within(devices).getByText('Unknown')).toBeInTheDocument()
  })

  it('reports API and database health', async () => {
    renderDashboard()
    const section = await card('System health')
    await waitFor(() => expect(within(section).getAllByText('Operational')).toHaveLength(2))
    expect(within(section).getByText('MySQL connected, 6 of 6 tables present')).toBeInTheDocument()
  })

  it('asks the API for the right things', async () => {
    const { api } = renderDashboard()
    await loaded()
    await waitFor(() => expect(api.callsTo('GET /api/history')).toHaveLength(1))
    expect(api.lastCall('GET /api/dashboard/activity').query).toEqual({ range: '24h' })
    expect(api.lastCall('GET /api/dashboard/top-destinations').query).toEqual({ range: '24h', limit: '6' })
    expect(api.lastCall('GET /api/dashboard/top-devices').query).toEqual({ range: '24h', limit: '6' })
    expect(api.lastCall('GET /api/reports/activity-by-node').query).toEqual({ range: '24h' })
    expect(api.lastCall('GET /api/history').query).toEqual({ pageSize: '8' })
    expect(api.lastCall('GET /api/devices').query).toEqual({ pageSize: '6' })
    expect(api.lastCall('GET /api/nodes').query).toEqual({ pageSize: '100' })
  })

  it('works for an analyst too', async () => {
    renderDashboard({}, { user: ANALYST })
    expect(await loaded()).toBeInTheDocument()
  })
})

describe('DashboardPage: interaction', () => {
  it('switches the time range for every range-dependent section', async () => {
    const { api } = renderDashboard()
    await loaded()
    expect(screen.getByRole('button', { name: '24 hours' })).toHaveAttribute('aria-pressed', 'true')

    await userEvent.click(screen.getByRole('button', { name: '7 days' }))
    await waitFor(() => expect(api.lastCall('GET /api/dashboard/activity').query.range).toBe('7d'))
    for (const key of ['GET /api/dashboard/top-destinations', 'GET /api/dashboard/top-devices', 'GET /api/reports/activity-by-node']) {
      await waitFor(() => expect(api.lastCall(key).query.range).toBe('7d'))
    }
    expect(screen.getByRole('button', { name: '7 days' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getAllByText(/the last 7 days/, { selector: 'p' }).length).toBeGreaterThanOrEqual(4)
    expect(screen.queryByText(/the last 24 hours/, { selector: 'p' })).not.toBeInTheDocument()
  })

  it('opens the event detail panel when a recent event is selected', async () => {
    const { api } = renderDashboard({ 'GET /api/history/101': historyEvent() })
    const section = await card('Recent network activity')
    await userEvent.click(await within(section).findByRole('row', { name: /PC-LAB-A-001/ }))

    expect(await screen.findByRole('dialog', { name: 'Event #101' })).toBeInTheDocument()
    expect(api.callsTo('GET /api/history/101')).toHaveLength(1)
    await userEvent.click(screen.getByRole('button', { name: 'Close panel' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('refreshes everything when Refresh is pressed', async () => {
    const { api } = renderDashboard()
    await loaded()
    await waitFor(() => expect(api.callsTo('GET /api/history')).toHaveLength(1))
    const before = api.callsTo('GET /api/dashboard/summary').length

    await userEvent.click(screen.getByRole('button', { name: 'Refresh dashboard' }))
    await waitFor(() => expect(api.callsTo('GET /api/dashboard/summary').length).toBe(before + 1))
    await waitFor(() => expect(api.callsTo('GET /api/history')).toHaveLength(2))
  })

  it('pauses and resumes live updates', async () => {
    renderDashboard()
    await loaded()
    const toggle = screen.getByRole('button', { name: 'Live' })
    expect(toggle).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(toggle)
    expect(screen.getByRole('button', { name: 'Paused' })).toHaveAttribute('aria-pressed', 'false')
    await userEvent.click(screen.getByRole('button', { name: 'Paused' }))
    expect(screen.getByRole('button', { name: 'Live' })).toBeInTheDocument()
  })

  it('refreshes by itself every 15 seconds while live, and stops when paused', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
    const { api } = renderDashboard()
    await loaded()
    const count = () => api.callsTo('GET /api/dashboard/summary').length
    const first = count()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(15000)
    })
    await waitFor(() => expect(count()).toBe(first + 1))

    await userEvent.click(screen.getByRole('button', { name: 'Live' }))
    const paused = count()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(45000)
    })
    expect(count()).toBe(paused)
  })
})

describe('DashboardPage: empty states', () => {
  it('explains each empty section instead of showing a blank card', async () => {
    renderDashboard({
      'GET /api/dashboard/summary': summary({ active_nodes: 0, registered_devices: 0, todays_events: 0, known_destinations: 0 }),
      'GET /api/dashboard/activity': activity({ points: [{ bucket: '2026-09-20T07:00:00', event_count: 0 }] }),
      'GET /api/dashboard/top-destinations': [],
      'GET /api/dashboard/top-devices': [],
      'GET /api/reports/activity-by-node': [],
      'GET /api/history': paginated([]),
      'GET /api/nodes': paginated([]),
      'GET /api/devices': paginated([]),
    })
    await loaded('0')
    expect(await within(await card('Network activity over time')).findByText('No activity in this period')).toBeInTheDocument()
    expect(within(await card('Top destinations')).getByText('No destinations in this period')).toBeInTheDocument()
    expect(within(await card('Activity by node')).getByText('No nodes registered')).toBeInTheDocument()
    expect(within(await card('Recent network activity')).getByText('No network activity yet')).toBeInTheDocument()
    expect(within(await card('Most active devices')).getByText('No device activity in this period')).toBeInTheDocument()
    expect(within(await card('Node status')).getByText('No nodes registered')).toBeInTheDocument()
    expect(within(await card('Recently seen devices')).getByText('No devices registered')).toBeInTheDocument()
    expect(within(kpi("Today's events")).getByText('0')).toBeInTheDocument()
  })
})

describe('DashboardPage: errors', () => {
  it('shows a banner and per-card errors when the summary cannot be loaded, and recovers on retry', async () => {
    const { api } = renderDashboard({
      'GET /api/dashboard/summary': reply(500, { detail: 'Internal server error' }),
      'GET /api/dashboard/activity': reply(500, { detail: 'Internal server error' }),
    })
    expect(await screen.findByText('Unable to load the dashboard summary: Internal server error')).toBeInTheDocument()

    const chartCard = await card('Network activity over time')
    expect(await within(chartCard).findByText('Unable to load this data')).toBeInTheDocument()
    expect(await within(await card('Recent network activity')).findByText('PC-LAB-A-001')).toBeInTheDocument()

    api.set('GET /api/dashboard/activity', activity())
    await userEvent.click(within(chartCard).getByRole('button', { name: 'Try again' }))
    expect(await within(chartCard).findByTestId('activity-chart')).toBeInTheDocument()
  })

  it('tells the user when the server cannot be reached at all', async () => {
    renderDashboard({
      'GET /api/dashboard/activity': reply(502, '<html>Bad Gateway</html>'),
    })
    expect(await within(await card('Network activity over time')).findByText('The server is unavailable. Please try again shortly.')).toBeInTheDocument()
  })

  it('keeps showing the last data, with one combined notice, when a refresh fails', async () => {
    const { api } = renderDashboard()
    await loaded()
    expect(within(kpi("Today's events")).getByText('22')).toBeInTheDocument()

    api.set('GET /api/dashboard/summary', reply(503, { detail: 'Temporarily unable, please retry' }))
    api.set('GET /api/dashboard/activity', reply(503, { detail: 'Temporarily unable, please retry' }))
    await userEvent.click(screen.getByRole('button', { name: 'Refresh dashboard' }))

    expect(await screen.findByText(/Showing the last data received/)).toBeInTheDocument()
    expect(screen.getAllByText(/Showing the last data received/)).toHaveLength(1)
    expect(screen.queryByText(/Could not refresh/)).not.toBeInTheDocument()
    expect(within(kpi("Today's events")).getByText('22')).toBeInTheDocument()

    api.set('GET /api/dashboard/summary', summary({ todays_events: 30 }))
    api.set('GET /api/dashboard/activity', activity())
    await userEvent.click(screen.getByRole('button', { name: 'Retry now' }))
    await waitFor(() => expect(screen.queryByText(/Showing the last data received/)).not.toBeInTheDocument())
    expect(within(kpi("Today's events")).getByText('30')).toBeInTheDocument()
  })
})
