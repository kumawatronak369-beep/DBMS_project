import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { reply } from '../test/fetchMock.js'
import { ADMIN, ANALYST, device, node, nodeDetail, paginated } from '../test/fixtures.js'
import { allPageRoutes, renderApp } from '../test/render.jsx'

const LAB_A = node()
const LAB_B = node({ node_id: 2, node_code: 'LAB-B', node_name: 'Computer Lab B', ip_address: '10.10.2.1', location: 'Science Block, First Floor', status: 'OFFLINE', last_seen: null })
const OLD = node({ node_id: 3, node_code: 'OLD-01', node_name: 'Retired Lab', ip_address: '10.10.9.1', location: 'Annex', status: 'INACTIVE', device_count: 0 })
const NODES = [LAB_A, LAB_B, OLD]

const renderNodes = ({ user = ADMIN, routes = {}, route = '/nodes' } = {}) =>
  renderApp(route, { user, routes: { 'GET /api/nodes': paginated(NODES), ...routes } })
const ready = () => screen.findByRole('row', { name: /Computer Lab A/ })
const row = (name) => screen.getByRole('row', { name: new RegExp(name) })

describe('NodesPage: listing', () => {
  it('lists every node with its details', async () => {
    renderNodes()
    await ready()
    expect(screen.getByRole('heading', { level: 1, name: 'Nodes' })).toBeInTheDocument()
    for (const name of ['Node', 'Location', 'Status', 'Devices', 'Last seen', 'Actions']) {
      expect(screen.getByRole('columnheader', { name })).toBeInTheDocument()
    }
    const labA = row('Computer Lab A')
    expect(within(labA).getByText('LAB-A · 10.10.1.1')).toBeInTheDocument()
    expect(within(labA).getByText('Science Block')).toBeInTheDocument()
    expect(within(labA).getByText('Active')).toBeInTheDocument()
    expect(within(labA).getByText('5')).toBeInTheDocument()
    expect(within(row('Computer Lab B')).getByText('Offline')).toBeInTheDocument()
    expect(within(row('Computer Lab B')).getByText('never')).toBeInTheDocument()
    expect(within(row('Retired Lab')).getByText('Inactive')).toBeInTheDocument()
  })

  it('asks the backend for the first page of 25', async () => {
    const { api } = renderNodes()
    await ready()
    expect(api.lastCall('GET /api/nodes').query).toEqual({ page: '1', pageSize: '25' })
  })

  it('shows a loading skeleton first', async () => {
    let release
    renderNodes({ routes: { 'GET /api/nodes': () => new Promise((resolve) => (release = () => resolve(paginated(NODES)))) } })
    expect(await screen.findByRole('status', { name: 'Loading' })).toBeInTheDocument()
    release()
    await ready()
    expect(screen.queryByRole('status', { name: 'Loading' })).not.toBeInTheDocument()
  })

  it('opens a node from its row, and from the view link', async () => {
    renderNodes({ routes: { 'GET /api/nodes/1': nodeDetail(), 'GET /api/devices': paginated([device()]) } })
    await ready()
    expect(screen.getByRole('link', { name: 'View Computer Lab A' })).toHaveAttribute('href', '/nodes/1')
    await userEvent.click(row('Computer Lab A'))
    expect(await screen.findByRole('heading', { level: 1, name: 'Computer Lab A' })).toBeInTheDocument()
  })
})

describe('NodesPage: search, filter and paging', () => {
  it('searches on the backend after a short pause, from page 1', async () => {
    const { api } = renderNodes({
      routes: { 'GET /api/nodes': ({ query }) => paginated(query.search === 'lab b' ? [LAB_B] : NODES) },
    })
    await ready()
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search nodes' }), 'lab b')

    await waitFor(() => expect(api.lastCall('GET /api/nodes').query.search).toBe('lab b'))
    await waitFor(() => expect(screen.queryByRole('row', { name: /Computer Lab A/ })).not.toBeInTheDocument())
    expect(row('Computer Lab B')).toBeInTheDocument()
    expect(api.lastCall('GET /api/nodes').query.page).toBe('1')
    expect(api.callsTo('GET /api/nodes').filter((call) => call.query.search).length).toBe(1)
  })

  it('filters by status', async () => {
    const { api } = renderNodes({ routes: { 'GET /api/nodes': ({ query }) => paginated(query.status === 'INACTIVE' ? [OLD] : NODES) } })
    await ready()
    await userEvent.selectOptions(screen.getByLabelText('Filter by status'), 'INACTIVE')
    await waitFor(() => expect(api.lastCall('GET /api/nodes').query.status).toBe('INACTIVE'))
    expect(await screen.findByRole('row', { name: /Retired Lab/ })).toBeInTheDocument()
    expect(screen.queryByRole('row', { name: /Computer Lab A/ })).not.toBeInTheDocument()
  })

  it('says nothing matches, and Clear brings everything back', async () => {
    const { api } = renderNodes({ routes: { 'GET /api/nodes': ({ query }) => paginated(query.search ? [] : NODES) } })
    await ready()
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search nodes' }), 'zzz')

    expect(await screen.findByText('No nodes match your filters')).toBeInTheDocument()
    expect(screen.getByText('Try changing or clearing the filters.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Clear' }))
    await ready()
    expect(api.lastCall('GET /api/nodes').query.search).toBeUndefined()
    expect(screen.getByRole('searchbox', { name: 'Search nodes' })).toHaveValue('')
  })

  it('moves through pages using the backend pagination', async () => {
    const { api } = renderNodes({
      routes: { 'GET /api/nodes': ({ query }) => paginated(NODES, { page: Number(query.page), total: 60 }) },
    })
    await ready()
    expect(screen.getByText('1–25 of 60')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Next page' }))
    await waitFor(() => expect(api.lastCall('GET /api/nodes').query.page).toBe('2'))
    expect(await screen.findByText('26–50 of 60')).toBeInTheDocument()
  })
})

describe('NodesPage: empty and error states', () => {
  it('invites an admin to add the first node', async () => {
    renderNodes({ routes: { 'GET /api/nodes': paginated([]) } })
    expect(await screen.findByText('No nodes registered yet')).toBeInTheDocument()
    expect(screen.getByText('Add a node to start monitoring.')).toBeInTheDocument()
  })

  it('does not suggest adding a node to an analyst', async () => {
    renderNodes({ user: ANALYST, routes: { 'GET /api/nodes': paginated([]) } })
    expect(await screen.findByText('No nodes registered yet')).toBeInTheDocument()
    expect(screen.queryByText('Add a node to start monitoring.')).not.toBeInTheDocument()
  })

  it('shows an error with a working retry', async () => {
    const { api } = renderNodes({ routes: { 'GET /api/nodes': reply(500, { detail: 'Internal server error' }) } })
    expect(await screen.findByText('Unable to load nodes')).toBeInTheDocument()
    expect(screen.getByText('Internal server error')).toBeInTheDocument()

    api.set('GET /api/nodes', paginated(NODES))
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    await ready()
    expect(screen.queryByText('Unable to load nodes')).not.toBeInTheDocument()
  })

  it('reports an unreachable server', async () => {
    renderNodes({ routes: { 'GET /api/nodes': reply(502, '<html>Bad gateway</html>') } })
    expect(await screen.findByText('The server is unavailable. Please try again shortly.')).toBeInTheDocument()
  })
})

describe('NodesPage: permissions', () => {
  it('gives an admin add, edit and disable/enable controls', async () => {
    renderNodes()
    await ready()
    expect(screen.getByRole('button', { name: 'Add node' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Edit Computer Lab A' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Disable Computer Lab A' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Enable Retired Lab' })).toBeInTheDocument()
  })

  it('gives an analyst read-only access', async () => {
    renderNodes({ user: ANALYST })
    await ready()
    expect(screen.queryByRole('button', { name: 'Add node' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Edit / })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^(Disable|Enable) / })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'View Computer Lab A' })).toBeInTheDocument()
  })
})

describe('NodesPage: admin actions', () => {
  it('adds a node and refreshes the list', async () => {
    let created = false
    const NEW = node({ node_id: 9, node_code: 'LAB-Z', node_name: 'Lab Z', ip_address: '10.0.0.9', location: 'Block Z' })
    const { api } = renderNodes({
      routes: {
        'GET /api/nodes': () => paginated(created ? [...NODES, NEW] : NODES),
        'POST /api/nodes': () => {
          created = true
          return reply(201, NEW)
        },
      },
    })
    await ready()
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Add node' }))
    const dialog = screen.getByRole('dialog', { name: 'Add node' })
    await user.type(within(dialog).getByLabelText('Node code'), 'LAB-Z')
    await user.type(within(dialog).getByLabelText('Name'), 'Lab Z')
    await user.type(within(dialog).getByLabelText('IP address'), '10.0.0.9')
    await user.type(within(dialog).getByLabelText('Location'), 'Block Z')
    await user.click(within(dialog).getByRole('button', { name: 'Add node' }))

    expect(await screen.findByRole('row', { name: /Lab Z/ })).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(api.lastCall('POST /api/nodes').body).toMatchObject({ node_code: 'LAB-Z', node_name: 'Lab Z', ip_address: '10.0.0.9', location: 'Block Z', description: null })
    expect(api.callsTo('GET /api/nodes')).toHaveLength(2)
  })

  it('keeps the form open and explains a rejected node', async () => {
    renderNodes({ routes: { 'POST /api/nodes': reply(409, { detail: "Node code 'LAB-A' is already in use" }) } })
    await ready()
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Add node' }))
    const dialog = screen.getByRole('dialog')
    await user.type(within(dialog).getByLabelText('Node code'), 'LAB-A')
    await user.type(within(dialog).getByLabelText('Name'), 'Duplicate')
    await user.type(within(dialog).getByLabelText('IP address'), '10.0.0.5')
    await user.type(within(dialog).getByLabelText('Location'), 'Here')
    await user.click(within(dialog).getByRole('button', { name: 'Add node' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent("Node code 'LAB-A' is already in use")
  })

  it('edits a node', async () => {
    const { api } = renderNodes({ routes: { 'PUT /api/nodes/1': { ...LAB_A, node_name: 'Renamed Lab' } } })
    await ready()
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Edit Computer Lab A' }))
    const dialog = screen.getByRole('dialog', { name: 'Edit Computer Lab A' })
    expect(within(dialog).getByLabelText('IP address')).toHaveValue('10.10.1.1')
    await user.clear(within(dialog).getByLabelText('Name'))
    await user.type(within(dialog).getByLabelText('Name'), 'Renamed Lab')
    await user.click(within(dialog).getByRole('button', { name: 'Save changes' }))

    await waitFor(() => expect(api.callsTo('PUT /api/nodes/1')).toHaveLength(1))
    expect(api.lastCall('PUT /api/nodes/1').body.node_name).toBe('Renamed Lab')
    await waitFor(() => expect(api.callsTo('GET /api/nodes')).toHaveLength(2))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('does not navigate to the node when an action button is clicked', async () => {
    renderNodes()
    await ready()
    await userEvent.click(screen.getByRole('button', { name: 'Edit Computer Lab A' }))
    expect(screen.getByRole('heading', { level: 1, name: 'Nodes' })).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('asks before disabling, and disabling keeps history (sets INACTIVE)', async () => {
    const { api } = renderNodes({ routes: { 'PATCH /api/nodes/1/status': { ...LAB_A, status: 'INACTIVE' } } })
    await ready()
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Disable Computer Lab A' }))
    const dialog = screen.getByRole('dialog', { name: 'Disable Computer Lab A?' })
    expect(within(dialog).getByText(/devices and history are preserved/)).toBeInTheDocument()

    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(api.callsTo('PATCH /api/nodes/1/status')).toHaveLength(0)

    await user.click(screen.getByRole('button', { name: 'Disable Computer Lab A' }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Disable node' }))
    await waitFor(() => expect(api.callsTo('PATCH /api/nodes/1/status')).toHaveLength(1))
    expect(api.lastCall('PATCH /api/nodes/1/status').body).toEqual({ status: 'INACTIVE' })
    await waitFor(() => expect(api.callsTo('GET /api/nodes')).toHaveLength(2))
  })

  it('re-enables an inactive node', async () => {
    const { api } = renderNodes({ routes: { 'PATCH /api/nodes/3/status': { ...OLD, status: 'ACTIVE' } } })
    await ready()
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Enable Retired Lab' }))
    expect(screen.getByRole('dialog', { name: 'Enable Retired Lab?' })).toBeInTheDocument()
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Enable node' }))
    await waitFor(() => expect(api.lastCall('PATCH /api/nodes/3/status')?.body).toEqual({ status: 'ACTIVE' }))
  })

  it('shows why a status change failed and leaves the dialog open', async () => {
    renderNodes({ routes: { 'PATCH /api/nodes/1/status': reply(500, { detail: 'Internal server error' }) } })
    await ready()
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Disable Computer Lab A' }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Disable node' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Internal server error')
    expect(screen.getByRole('dialog', { name: 'Disable Computer Lab A?' })).toBeInTheDocument()
  })
})

describe('NodesPage: linked from other pages', () => {
  it('is reachable from the sidebar with the whole app wired up', async () => {
    renderApp('/dashboard', { routes: allPageRoutes() })
    await screen.findByRole('heading', { level: 1, name: 'Dashboard' })
    await userEvent.click(within(screen.getByRole('navigation', { name: 'Main navigation' })).getByRole('link', { name: 'Nodes' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Nodes' })).toBeInTheDocument()
  })
})
