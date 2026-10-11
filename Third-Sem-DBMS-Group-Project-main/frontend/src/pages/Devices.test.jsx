import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { reply } from '../test/fetchMock.js'
import { device, deviceDetail, historyEvent, node, nodeDetail, paginated } from '../test/fixtures.js'
import { renderApp } from '../test/render.jsx'

const PC1 = device()
const PC2 = device({ device_id: 2, device_identifier: 'PC-LAB-B-002', device_name: null, hostname: null, node_id: 2, node_name: 'Computer Lab B', ip_address: '192.168.20.22', status: 'UNKNOWN' })
const NODES = paginated([node(), node({ node_id: 2, node_code: 'LAB-B', node_name: 'Computer Lab B' })])

const renderDevices = ({ routes = {}, route = '/devices' } = {}) =>
  renderApp(route, { routes: { 'GET /api/devices': paginated([PC1, PC2]), 'GET /api/nodes': NODES, ...routes } })
const ready = () => screen.findByRole('row', { name: /PC-LAB-A-001/ })

describe('DevicesPage', () => {
  it('lists devices with everything the spec asks for', async () => {
    renderDevices()
    await ready()
    for (const name of ['Device', 'IP address', 'Hostname', 'Node', 'First seen', 'Last seen', 'Status']) {
      expect(screen.getByRole('columnheader', { name })).toBeInTheDocument()
    }
    const first = screen.getByRole('row', { name: /PC-LAB-A-001/ })
    expect(within(first).getByText('LAB-A Workstation 1')).toBeInTheDocument()
    expect(within(first).getByText('192.168.10.21')).toBeInTheDocument()
    expect(within(first).getByText('pc-lab-a-001.campus.local')).toBeInTheDocument()
    expect(within(first).getByRole('link', { name: 'Computer Lab A' })).toHaveAttribute('href', '/nodes/1')
    expect(within(first).getByText('Active')).toBeInTheDocument()

    const second = screen.getByRole('row', { name: /PC-LAB-B-002/ })
    expect(within(second).getByText('—')).toBeInTheDocument()
    expect(within(second).getByText('Unknown')).toBeInTheDocument()
  })

  it('offers the node filter from the node list and applies it', async () => {
    const { api } = renderDevices()
    await ready()
    const select = screen.getByLabelText('Filter by node')
    await waitFor(() => expect(within(select).getByRole('option', { name: 'Computer Lab B' })).toBeInTheDocument())
    await userEvent.selectOptions(select, 'Computer Lab B')
    await waitFor(() => expect(api.lastCall('GET /api/devices').query.nodeId).toBe('2'))
  })

  it('starts filtered when opened from a node ("View all devices")', async () => {
    const { api } = renderDevices({ route: '/devices?nodeId=1&status=ACTIVE' })
    await ready()
    expect(api.lastCall('GET /api/devices').query).toMatchObject({ nodeId: '1', status: 'ACTIVE', page: '1' })
    await waitFor(() => expect(screen.getByLabelText('Filter by node')).toHaveValue('1'))
    expect(screen.getByLabelText('Filter by status')).toHaveValue('ACTIVE')
  })

  it('searches and filters by status on the backend', async () => {
    const { api } = renderDevices()
    await ready()
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search devices' }), '192.168.20')
    await waitFor(() => expect(api.lastCall('GET /api/devices').query.search).toBe('192.168.20'))
    await userEvent.selectOptions(screen.getByLabelText('Filter by status'), 'UNKNOWN')
    await waitFor(() => expect(api.lastCall('GET /api/devices').query.status).toBe('UNKNOWN'))
  })

  it('pages through results', async () => {
    const { api } = renderDevices({ routes: { 'GET /api/devices': ({ query }) => paginated([PC1], { page: Number(query.page), total: 80 }) } })
    await ready()
    expect(screen.getByText('1–25 of 80')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Next page' }))
    await waitFor(() => expect(api.lastCall('GET /api/devices').query.page).toBe('2'))
  })

  it('opens a device from its row, but the node link goes to the node', async () => {
    renderDevices({
      routes: { 'GET /api/devices/1': deviceDetail(), 'GET /api/devices/1/history': paginated([]), 'GET /api/nodes/1': nodeDetail(), 'GET /api/nodes': NODES },
    })
    await ready()
    await userEvent.click(within(screen.getByRole('row', { name: /PC-LAB-A-001/ })).getByRole('link', { name: 'Computer Lab A' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Computer Lab A' })).toBeInTheDocument()
  })

  it('opens the device page when the row itself is clicked', async () => {
    renderDevices({ routes: { 'GET /api/devices/1': deviceDetail(), 'GET /api/devices/1/history': paginated([]) } })
    await ready()
    await userEvent.click(screen.getByRole('row', { name: /PC-LAB-A-001/ }))
    expect(await screen.findByRole('heading', { level: 1, name: 'PC-LAB-A-001' })).toBeInTheDocument()
  })

  it('explains empty results and offers Clear', async () => {
    renderDevices({ route: '/devices?search=zzz', routes: { 'GET /api/devices': paginated([]) } })
    expect(await screen.findByText('No devices match your filters')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Clear' })).toBeInTheDocument()
  })

  it('says there are no devices yet when nothing is registered', async () => {
    renderDevices({ routes: { 'GET /api/devices': paginated([]) } })
    expect(await screen.findByText('No devices found')).toBeInTheDocument()
    expect(screen.getByText('Devices appear when a node reports events.')).toBeInTheDocument()
  })

  it('shows loading and error states, with retry', async () => {
    const { api } = renderDevices({ routes: { 'GET /api/devices': reply(500, { detail: 'Internal server error' }) } })
    expect(await screen.findByText('Unable to load devices')).toBeInTheDocument()
    api.set('GET /api/devices', paginated([PC1]))
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    await ready()
  })
})

describe('DeviceDetailPage', () => {
  const detailRoutes = (over = {}) => ({
    'GET /api/devices/1': deviceDetail(),
    'GET /api/devices/1/history': paginated([historyEvent()], { pageSize: 10 }),
    'GET /api/history/101': historyEvent(),
    ...over,
  })
  const renderDetail = (over = {}, route = '/devices/1') => renderApp(route, { routes: detailRoutes(over) })
  const heading = () => screen.findByRole('heading', { level: 1, name: 'PC-LAB-A-001' })
  const card = (title) => screen.getByRole('heading', { name: title }).closest('section')

  it('shows the device, its metadata and its numbers', async () => {
    renderDetail()
    await heading()
    expect(screen.getAllByText('LAB-A Workstation 1').length).toBeGreaterThan(0)
    expect(document.title).toBe('PC-LAB-A-001 · NetMonitor')
    const details = card('Device details')
    for (const text of ['192.168.10.21', '02:00:01:00:00:01', 'pc-lab-a-001.campus.local']) {
      expect(within(details).getByText(text)).toBeInTheDocument()
    }
    expect(within(details).getByRole('link', { name: 'Computer Lab A' })).toHaveAttribute('href', '/nodes/1')
    expect(within(details).getByText(/rather than guessed/)).toBeInTheDocument()
    expect(screen.getByText('Stored events').closest('div')).toHaveTextContent('57')
    expect(within(card('Activity, last 7 days')).getByTestId('activity-chart')).toHaveAttribute('data-total', '9')
  })

  it('lists recent destinations with links', async () => {
    renderDetail()
    await heading()
    const section = card('Recent destinations')
    const row = within(section).getByRole('row', { name: /github\.com/ })
    expect(within(row).getByText('203.0.113.20')).toBeInTheDocument()
    expect(within(row).getByText('Development')).toBeInTheDocument()
    expect(within(row).getByText('10')).toBeInTheDocument()
  })

  it('shows its own network history, newest first, without repeating the device column', async () => {
    const { api } = renderDetail()
    await heading()
    const history = card('Network history')
    expect(await within(history).findByText('github.com')).toBeInTheDocument()
    expect(within(history).queryByRole('columnheader', { name: 'Device' })).not.toBeInTheDocument()
    expect(api.lastCall('GET /api/devices/1/history').query).toEqual({ page: '1', pageSize: '10' })
  })

  it('narrows the history to a time range and goes back to page 1', async () => {
    const { api } = renderDetail({ 'GET /api/devices/1/history': ({ query }) => paginated([historyEvent()], { page: Number(query.page), total: 40, pageSize: 10 }) })
    await heading()
    const history = card('Network history')
    await within(history).findByText('github.com')
    await userEvent.click(within(history).getByRole('button', { name: 'Next page' }))
    await waitFor(() => expect(api.lastCall('GET /api/devices/1/history').query.page).toBe('2'))

    await userEvent.click(within(history).getByRole('button', { name: '7 days' }))
    await waitFor(() => expect(api.lastCall('GET /api/devices/1/history').query).toEqual({ range: '7d', page: '1', pageSize: '10' }))
    expect(within(history).getByRole('button', { name: '7 days' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('opens the event panel from the history', async () => {
    renderDetail()
    await heading()
    await userEvent.click(await within(card('Network history')).findByRole('row', { name: /github\.com/ }))
    expect(await screen.findByRole('dialog', { name: 'Event #101' })).toBeInTheDocument()
  })

  it('explains an empty history differently for "all time" and a narrower range', async () => {
    renderDetail({ 'GET /api/devices/1/history': paginated([]) })
    await heading()
    const history = card('Network history')
    expect(await within(history).findByText('No network activity found')).toBeInTheDocument()
    expect(within(history).getByText('No events have been stored yet.')).toBeInTheDocument()
    await userEvent.click(within(history).getByRole('button', { name: '24 hours' }))
    expect(await within(history).findByText('Try a longer time range.')).toBeInTheDocument()
  })

  it('handles a device with no events or destinations yet', async () => {
    renderDetail({ 'GET /api/devices/1': deviceDetail({ total_events: 0, recent_destinations: [] }), 'GET /api/devices/1/history': paginated([]) })
    await heading()
    expect(within(card('Activity, last 7 days')).getByText('No activity yet')).toBeInTheDocument()
    expect(within(card('Recent destinations')).getByText('No destinations yet')).toBeInTheDocument()
  })

  it('shows a dash for details that were never observed', async () => {
    renderDetail({ 'GET /api/devices/1': deviceDetail({ mac_address: null, hostname: null, device_name: null }) })
    expect(await screen.findByRole('heading', { level: 1, name: 'PC-LAB-A-001' })).toBeInTheDocument()
    expect(within(card('Device details')).getAllByText('—').length).toBeGreaterThanOrEqual(3)
    expect(screen.getByText('Observed through Computer Lab A')).toBeInTheDocument()
  })

  it('shows "Not found" with a way back for an unknown device', async () => {
    renderDetail({ 'GET /api/devices/9': reply(404, { detail: 'Device 9 not found' }) }, '/devices/9')
    expect(await screen.findByText('Not found')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to devices' })).toHaveAttribute('href', '/devices')
  })

  it('shows an error with retry when the device cannot be loaded', async () => {
    const { api } = renderDetail({ 'GET /api/devices/1': reply(500, { detail: 'Internal server error' }) })
    expect(await screen.findByText('Unable to load this device')).toBeInTheDocument()
    api.set('GET /api/devices/1', deviceDetail())
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    await heading()
  })

  it('shows an error card for the history without hiding the device', async () => {
    renderDetail({ 'GET /api/devices/1/history': reply(500, { detail: 'Internal server error' }) })
    await heading()
    expect(await within(card('Network history')).findByText('Unable to load network history')).toBeInTheDocument()
    expect(within(card('Device details')).getByText('192.168.10.21')).toBeInTheDocument()
  })
})
