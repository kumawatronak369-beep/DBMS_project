import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { reply } from '../test/fetchMock.js'
import { destination, historyEvent, node, paginated } from '../test/fixtures.js'
import { renderApp } from '../test/render.jsx'

const EVENTS = [
  historyEvent(),
  historyEvent({ history_id: 102, device_identifier: 'PC-LAB-B-002', device_ip: '192.168.20.22', node_name: 'Computer Lab B', domain: null, destination_ip: '192.0.2.77' }),
]

const renderHistory = ({ routes = {}, route = '/history' } = {}) =>
  renderApp(route, {
    routes: {
      'GET /api/history': paginated(EVENTS),
      'GET /api/nodes': paginated([node(), node({ node_id: 2, node_name: 'Computer Lab B' })]),
      'GET /api/destinations': paginated([destination(), destination({ destination_id: 3, domain: 'example.com' })]),
      'GET /api/history/101': historyEvent(),
      ...routes,
    },
  })
const ready = () => screen.findByRole('row', { name: /PC-LAB-A-001/ })

// userEvent.type can't fill a date input in jsdom, so set it through the native setter
function setDate(input, value) {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, value)
  input.dispatchEvent(new Event('input', { bubbles: true }))
}

describe('HistoryPage', () => {
  it('lists events, with a total in the subtitle', async () => {
    renderHistory()
    await ready()
    expect(screen.getByText('2 stored events')).toBeInTheDocument()
    expect(within(screen.getByRole('row', { name: /PC-LAB-B-002/ })).getByText('192.0.2.77')).toBeInTheDocument()
  })

  it('sends nothing but paging when no filter is set', async () => {
    const { api } = renderHistory()
    await ready()
    expect(api.lastCall('GET /api/history').query).toEqual({ page: '1', pageSize: '25' })
  })

  it('starts from filters found in the URL and shows them in the form', async () => {
    const { api } = renderHistory({ route: '/history?q=github&nodeId=1&startDate=2026-09-01&endDate=2026-09-19' })
    await ready()
    expect(api.lastCall('GET /api/history').query).toMatchObject({ q: 'github', nodeId: '1', startDate: '2026-09-01', endDate: '2026-09-19' })
    expect(screen.getByLabelText('Search device, IP or domain')).toHaveValue('github')
    expect(screen.getByLabelText('From date')).toHaveValue('2026-09-01')
    expect(screen.getByText('2 stored events match your filters')).toBeInTheDocument()
  })

  it('only applies the filters when Search is pressed', async () => {
    const { api } = renderHistory()
    await ready()
    const before = api.callsTo('GET /api/history').length
    await userEvent.type(screen.getByLabelText('Search device, IP or domain'), '  github  ')
    expect(api.callsTo('GET /api/history')).toHaveLength(before)
    await waitFor(() => expect(within(screen.getByLabelText('Node')).getByRole('option', { name: 'Computer Lab B' })).toBeInTheDocument())
    await waitFor(() => expect(within(screen.getByLabelText('Destination')).getByRole('option', { name: 'example.com' })).toBeInTheDocument())
    await userEvent.selectOptions(screen.getByLabelText('Node'), 'Computer Lab B')
    await userEvent.selectOptions(screen.getByLabelText('Destination'), 'example.com')
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => expect(api.lastCall('GET /api/history').query).toMatchObject({ q: 'github', nodeId: '2', destinationId: '3', page: '1' }))
  })

  it('refuses a start date after the end date', async () => {
    const { api } = renderHistory()
    await ready()
    const before = api.callsTo('GET /api/history').length
    setDate(screen.getByLabelText('From date'), '2026-09-19')
    setDate(screen.getByLabelText('To date'), '2026-09-01')
    expect(await screen.findByText('Start date is after the end date')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Search' })).toBeDisabled()
    expect(api.callsTo('GET /api/history')).toHaveLength(before)
  })

  it('clears all filters', async () => {
    const { api } = renderHistory({ route: '/history?q=github&nodeId=1' })
    await ready()
    await userEvent.click(screen.getByRole('button', { name: 'Clear' }))
    await waitFor(() => expect(api.lastCall('GET /api/history').query).toEqual({ page: '1', pageSize: '25' }))
    expect(screen.getByLabelText('Search device, IP or domain')).toHaveValue('')
    expect(screen.queryByRole('button', { name: 'Clear' })).not.toBeInTheDocument()
  })

  it('changes rows per page and pages through results', async () => {
    const { api } = renderHistory({
      routes: { 'GET /api/history': ({ query }) => paginated(EVENTS, { page: Number(query.page), pageSize: Number(query.pageSize), total: 240 }) },
    })
    await ready()
    await userEvent.click(screen.getByRole('button', { name: 'Next page' }))
    await waitFor(() => expect(api.lastCall('GET /api/history').query.page).toBe('2'))
    await userEvent.selectOptions(screen.getByLabelText('Rows per page'), '50')
    await waitFor(() => expect(api.lastCall('GET /api/history').query.pageSize).toBe('50'))
  })

  it('opens and closes the event detail panel', async () => {
    renderHistory()
    await userEvent.click(await ready())
    const dialog = await screen.findByRole('dialog', { name: 'Event #101' })
    expect(within(dialog).getAllByText(/github\.com/).length).toBeGreaterThan(0)
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('shows the connection details of an event in its panel', async () => {
    renderHistory({
      routes: { 'GET /api/history/101': historyEvent({ protocol: 'TCP', source_port: 56188, destination_port: 443 }) },
    })
    await userEvent.click(await ready())
    const dialog = await screen.findByRole('dialog', { name: 'Event #101' })
    const connection = within(dialog).getByRole('heading', { name: 'Connection' }).closest('section')
    expect(within(connection).getByText('TCP')).toBeInTheDocument()
    expect(within(connection).getByText('56188')).toBeInTheDocument()
    expect(within(connection).getByText('443')).toBeInTheDocument()
  })

  it('shows dashes in the panel for an event without connection details', async () => {
    renderHistory()
    await userEvent.click(await ready())
    const dialog = await screen.findByRole('dialog', { name: 'Event #101' })
    const connection = within(dialog).getByRole('heading', { name: 'Connection' }).closest('section')
    expect(within(connection).getAllByText('—')).toHaveLength(3)
  })

  it('has different empty messages with and without filters', async () => {
    const { unmount } = renderHistory({ routes: { 'GET /api/history': paginated([]) } })
    expect(await screen.findByText('No network activity found')).toBeInTheDocument()
    expect(screen.getByText('No events have been stored yet.')).toBeInTheDocument()
    unmount()
    renderHistory({ route: '/history?q=zzz', routes: { 'GET /api/history': paginated([]) } })
    expect(await screen.findByText('No network activity found')).toBeInTheDocument()
    expect(screen.getByText('Try changing your filters.')).toBeInTheDocument()
  })

  it('shows an error with retry, and recovers', async () => {
    const { api } = renderHistory({ routes: { 'GET /api/history': reply(500, { detail: 'Internal server error' }) } })
    expect(await screen.findByText('Unable to load network history')).toBeInTheDocument()
    api.set('GET /api/history', paginated(EVENTS))
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    await ready()
  })
})
