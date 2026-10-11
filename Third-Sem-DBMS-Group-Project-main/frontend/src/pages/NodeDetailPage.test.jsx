import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { reply } from '../test/fetchMock.js'
import { ADMIN, ANALYST, device, deviceDetail, historyEvent, node, nodeDetail, paginated } from '../test/fixtures.js'
import { renderApp } from '../test/render.jsx'

const routesFor = (detail = nodeDetail(), extra = {}) => ({
  'GET /api/nodes/1': detail,
  'GET /api/devices': paginated([device(), device({ device_id: 2, device_identifier: 'PC-LAB-A-002', status: 'INACTIVE' })]),
  'GET /api/history/101': historyEvent(),
  ...extra,
})
const renderDetail = ({ user = ADMIN, routes = routesFor(), route = '/nodes/1' } = {}) => renderApp(route, { user, routes })
const heading = (name = 'Computer Lab A') => screen.findByRole('heading', { level: 1, name })
const card = (title) => screen.getByRole('heading', { name: title }).closest('section')

describe('NodeDetailPage: content', () => {
  it('shows the node, its key numbers and its information', async () => {
    renderDetail()
    await heading()
    expect(screen.getByText('LAB-A · Science Block')).toBeInTheDocument()
    expect(document.title).toBe('Computer Lab A · NetMonitor')

    const info = card('Basic information')
    for (const text of ['LAB-A', 'Computer Lab A', '10.10.1.1', 'Science Block']) {
      expect(within(info).getByText(text)).toBeInTheDocument()
    }
    expect(within(info).getAllByText('—').length).toBeGreaterThan(0)

    expect(screen.getByText('Stored events').closest('div')).toHaveTextContent('260')
    expect(screen.getByText('Devices', { selector: 'p' }).closest('div')).toHaveTextContent('5')
  })

  it('draws the 7-day activity and lists recent activity', async () => {
    renderDetail()
    await heading()
    const chart = within(card('Activity, last 7 days')).getByTestId('activity-chart')
    expect(chart).toHaveAttribute('data-bucket', 'day')
    expect(chart).toHaveAttribute('data-total', '50')

    const recent = card('Recent activity')
    expect(within(recent).getByText('PC-LAB-A-001')).toBeInTheDocument()
    expect(within(recent).getByText('github.com')).toBeInTheDocument()
    expect(within(recent).queryByRole('columnheader', { name: 'Node' })).not.toBeInTheDocument()
    expect(within(recent).getByRole('link', { name: 'Open history' })).toHaveAttribute('href', '/history?nodeId=1')
  })

  it("lists the node's devices and links to the full list", async () => {
    const { api } = renderDetail()
    await heading()
    const devices = card('Devices')
    expect(await within(devices).findByText('PC-LAB-A-002')).toBeInTheDocument()
    expect(within(devices).getByText('Inactive')).toBeInTheDocument()
    expect(within(devices).getByRole('link', { name: 'View all' })).toHaveAttribute('href', '/devices?nodeId=1')
    expect(api.lastCall('GET /api/devices').query).toEqual({ nodeId: '1', pageSize: '8' })
  })

  it('opens a device from the list', async () => {
    renderDetail({
      routes: routesFor(nodeDetail(), {
        'GET /api/devices/2': deviceDetail({ device_id: 2, device_identifier: 'PC-LAB-A-002' }),
        'GET /api/devices/2/history': paginated([]),
      }),
    })
    await heading()
    await userEvent.click(await within(card('Devices')).findByRole('row', { name: /PC-LAB-A-002/ }))
    expect(await screen.findByRole('heading', { level: 1, name: 'PC-LAB-A-002' })).toBeInTheDocument()
  })

  it('opens the event panel from recent activity', async () => {
    renderDetail()
    await heading()
    await userEvent.click(within(card('Recent activity')).getByRole('row', { name: /PC-LAB-A-001/ }))
    expect(await screen.findByRole('dialog', { name: 'Event #101' })).toBeInTheDocument()
  })
})

describe('NodeDetailPage: empty states', () => {
  it('explains a node that has not reported anything yet', async () => {
    renderDetail({
      routes: routesFor(nodeDetail({ event_count: 0, device_count: 0, recent_activity: [], last_seen: null }), {
        'GET /api/devices': paginated([]),
      }),
    })
    await heading()
    expect(within(card('Activity, last 7 days')).getByText('No activity yet')).toBeInTheDocument()
    expect(within(card('Recent activity')).getByText('No recent activity')).toBeInTheDocument()
    expect(await within(card('Devices')).findByText('No devices yet')).toBeInTheDocument()
    expect(screen.getAllByText('never').length).toBeGreaterThan(0)
  })
})

describe('NodeDetailPage: errors', () => {
  it('shows "Not found" with a way back (and no pointless retry) for an unknown node', async () => {
    renderDetail({ route: '/nodes/999', routes: { 'GET /api/nodes/999': reply(404, { detail: 'Node 999 not found' }) } })
    expect(await screen.findByText('Not found')).toBeInTheDocument()
    expect(screen.getByText('Node 999 not found')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to nodes' })).toHaveAttribute('href', '/nodes')
  })

  it('offers a retry for a server error and recovers', async () => {
    const { api } = renderDetail({ routes: routesFor(reply(500, { detail: 'Internal server error' })) })
    expect(await screen.findByText('Unable to load this node')).toBeInTheDocument()
    api.set('GET /api/nodes/1', nodeDetail())
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    await heading()
  })

  it('shows a skeleton while loading', async () => {
    let release
    renderDetail({ routes: routesFor(undefined, { 'GET /api/nodes/1': () => new Promise((resolve) => (release = () => resolve(nodeDetail()))) }) })
    expect(await screen.findByRole('status', { name: 'Loading' })).toBeInTheDocument()
    release()
    await heading()
  })

  it('shows an error card for the devices list without breaking the page', async () => {
    renderDetail({ routes: routesFor(nodeDetail(), { 'GET /api/devices': reply(500, { detail: 'Internal server error' }) }) })
    await heading()
    expect(await within(card('Devices')).findByText('Unable to load this data')).toBeInTheDocument()
    expect(within(card('Basic information')).getByText('10.10.1.1')).toBeInTheDocument()
  })
})

describe('NodeDetailPage: admin controls', () => {
  it('lets an admin edit and disable, and hides both from an analyst', async () => {
    const { unmount } = renderDetail({ user: ADMIN })
    await heading()
    expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Disable' })).toBeInTheDocument()
    unmount()

    renderDetail({ user: ANALYST })
    await heading()
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Disable' })).not.toBeInTheDocument()
  })

  it('edits the node and reloads it', async () => {
    const { api } = renderDetail({ routes: routesFor(nodeDetail(), { 'PUT /api/nodes/1': node({ node_name: 'Renamed Lab' }) }) })
    await heading()
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Edit' }))
    const dialog = screen.getByRole('dialog', { name: 'Edit Computer Lab A' })
    await user.clear(within(dialog).getByLabelText('Name'))
    await user.type(within(dialog).getByLabelText('Name'), 'Renamed Lab')
    await user.click(within(dialog).getByRole('button', { name: 'Save changes' }))

    await waitFor(() => expect(api.callsTo('PUT /api/nodes/1')).toHaveLength(1))
    await waitFor(() => expect(api.callsTo('GET /api/nodes/1')).toHaveLength(2))
  })

  it('disables the node after confirmation', async () => {
    const { api } = renderDetail({ routes: routesFor(nodeDetail(), { 'PATCH /api/nodes/1/status': node({ status: 'INACTIVE' }) }) })
    await heading()
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Disable' }))
    await user.click(within(screen.getByRole('dialog', { name: 'Disable Computer Lab A?' })).getByRole('button', { name: 'Disable node' }))
    await waitFor(() => expect(api.lastCall('PATCH /api/nodes/1/status')?.body).toEqual({ status: 'INACTIVE' }))
    await waitFor(() => expect(api.callsTo('GET /api/nodes/1')).toHaveLength(2))
  })

  it('offers "Enable" for an inactive node', async () => {
    renderDetail({ routes: routesFor(nodeDetail({ status: 'INACTIVE' })) })
    await heading()
    expect(screen.getByRole('button', { name: 'Enable' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Disable' })).not.toBeInTheDocument()
  })
})
