import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { reply } from '../test/fetchMock.js'
import { deviceDetail, destination, destinationDetail, historyEvent, paginated } from '../test/fixtures.js'
import { renderApp } from '../test/render.jsx'

const GITHUB = destination()
const UNRESOLVED = destination({ destination_id: 12, domain: null, ip_address: '192.0.2.77', category: 'UNKNOWN', event_count: 5, unique_devices: 2 })

const renderList = ({ routes = {}, route = '/destinations' } = {}) =>
  renderApp(route, { routes: { 'GET /api/destinations': paginated([GITHUB, UNRESOLVED]), ...routes } })
const ready = () => screen.findByRole('row', { name: /github\.com/ })

describe('DestinationsPage', () => {
  it('lists destinations with counts and dates', async () => {
    renderList()
    await ready()
    for (const name of ['Destination', 'IP address', 'Category', 'Events', 'Devices', 'First seen', 'Last seen']) {
      expect(screen.getByRole('columnheader', { name })).toBeInTheDocument()
    }
    const row = screen.getByRole('row', { name: /github\.com/ })
    expect(within(row).getByText('203.0.113.20')).toBeInTheDocument()
    expect(within(row).getByText('Development')).toBeInTheDocument()
    expect(within(row).getByText('98')).toBeInTheDocument()
    expect(within(row).getByText('17')).toBeInTheDocument()
    expect(screen.getByText(/not a security classification/)).toBeInTheDocument()
  })

  it('marks a destination without a domain as unresolved instead of inventing a name', async () => {
    renderList()
    await ready()
    const row = screen.getByRole('row', { name: /192\.0\.2\.77/ })
    expect(within(row).getByText('(unresolved)')).toBeInTheDocument()
    expect(within(row).getByText('Unknown')).toBeInTheDocument()
  })

  it('searches and filters by category on the backend', async () => {
    const { api } = renderList()
    await ready()
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search destinations' }), 'git')
    await waitFor(() => expect(api.lastCall('GET /api/destinations').query.search).toBe('git'))
    await userEvent.selectOptions(screen.getByLabelText('Filter by category'), 'DEVELOPMENT')
    await waitFor(() => expect(api.lastCall('GET /api/destinations').query.category).toBe('DEVELOPMENT'))
  })

  it('pages, and explains empty results', async () => {
    const { api } = renderList({ routes: { 'GET /api/destinations': ({ query }) => paginated([GITHUB], { page: Number(query.page), total: 60 }) } })
    await ready()
    await userEvent.click(screen.getByRole('button', { name: 'Next page' }))
    await waitFor(() => expect(api.lastCall('GET /api/destinations').query.page).toBe('2'))
  })

  it('has a filtered-empty and a truly-empty message', async () => {
    const { unmount } = renderList({ route: '/destinations?category=VIDEO', routes: { 'GET /api/destinations': paginated([]) } })
    expect(await screen.findByText('No destinations match your filters')).toBeInTheDocument()
    unmount()
    renderList({ routes: { 'GET /api/destinations': paginated([]) } })
    expect(await screen.findByText('No destinations found')).toBeInTheDocument()
    expect(screen.getByText('Destinations appear as collectors report activity.')).toBeInTheDocument()
  })

  it('shows an error with retry', async () => {
    const { api } = renderList({ routes: { 'GET /api/destinations': reply(500, { detail: 'Internal server error' }) } })
    expect(await screen.findByText('Unable to load destinations')).toBeInTheDocument()
    api.set('GET /api/destinations', paginated([GITHUB]))
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    await ready()
  })

  it('opens the investigation page from a row', async () => {
    renderList({ routes: { 'GET /api/destinations/2': destinationDetail(), 'GET /api/destinations/2/history': paginated([]) } })
    await ready()
    await userEvent.click(screen.getByRole('row', { name: /github\.com/ }))
    expect(await screen.findByRole('heading', { level: 1, name: 'github.com' })).toBeInTheDocument()
  })
})

describe('DestinationDetailPage', () => {
  const routesFor = (over = {}) => ({
    'GET /api/destinations/2': destinationDetail(),
    'GET /api/destinations/2/history': paginated([historyEvent()], { pageSize: 10 }),
    'GET /api/history/101': historyEvent(),
    ...over,
  })
  const renderDetail = (over = {}, route = '/destinations/2') => renderApp(route, { routes: routesFor(over) })
  const heading = (name = 'github.com') => screen.findByRole('heading', { level: 1, name })
  const card = (title) => screen.getByRole('heading', { name: title }).closest('section')

  it('shows everything the investigation page must show', async () => {
    renderDetail()
    await heading()
    expect(screen.getByText('203.0.113.20', { selector: 'p' })).toBeInTheDocument()
    const details = card('Destination details')
    expect(within(details).getByText('github.com')).toBeInTheDocument()
    expect(within(details).getByText('203.0.113.20')).toBeInTheDocument()
    expect(within(details).getByText('Development')).toBeInTheDocument()
    expect(within(details).getByText(/not a security classification/)).toBeInTheDocument()
    expect(screen.getByText('Total events').closest('div')).toHaveTextContent('98')
    expect(screen.getByText('Unique devices').closest('div')).toHaveTextContent('17')
  })

  it('lists the nodes that saw it and the devices that accessed it', async () => {
    renderDetail()
    await heading()
    const nodes = card('Associated nodes')
    expect(within(nodes).getByRole('link', { name: /Computer Lab A/ })).toHaveAttribute('href', '/nodes/1')
    expect(within(nodes).getByText('37 events')).toBeInTheDocument()

    const devices = card('Devices accessing this destination')
    const row = within(devices).getByRole('row', { name: /PC-LAB-A-001/ })
    expect(within(row).getByText('10')).toBeInTheDocument()
    expect(within(row).getByText(/Computer Lab A · last/)).toBeInTheDocument()
  })

  it('opens a device from the access list', async () => {
    renderDetail({ 'GET /api/devices/1': deviceDetail(), 'GET /api/devices/1/history': paginated([]) })
    await heading()
    await userEvent.click(within(card('Devices accessing this destination')).getByRole('row', { name: /PC-LAB-A-001/ }))
    expect(await screen.findByRole('heading', { level: 1, name: 'PC-LAB-A-001' })).toBeInTheDocument()
  })

  it('shows recent access with time filtering', async () => {
    const { api } = renderDetail()
    await heading()
    const recent = card('Recent access')
    expect(await within(recent).findByText('PC-LAB-A-001')).toBeInTheDocument()
    expect(api.lastCall('GET /api/destinations/2/history').query).toEqual({ page: '1', pageSize: '10' })
    await userEvent.click(within(recent).getByRole('button', { name: '30 days' }))
    await waitFor(() => expect(api.lastCall('GET /api/destinations/2/history').query.range).toBe('30d'))
  })

  it('uses the IP as the title when no domain was observed, and says so', async () => {
    renderDetail(
      { 'GET /api/destinations/12': destinationDetail({ destination_id: 12, domain: null, ip_address: '192.0.2.77', category: 'UNKNOWN' }), 'GET /api/destinations/12/history': paginated([]) },
      '/destinations/12',
    )
    await heading('192.0.2.77')
    expect(screen.getByText('No DNS name was observed for this destination')).toBeInTheDocument()
    expect(within(card('Destination details')).getByText('Not observed')).toBeInTheDocument()
  })

  it('handles a destination nobody has reached yet', async () => {
    renderDetail({ 'GET /api/destinations/2': destinationDetail({ nodes: [], devices: [], event_count: 0, unique_devices: 0 }), 'GET /api/destinations/2/history': paginated([]) })
    await heading()
    expect(within(card('Associated nodes')).getByText('No nodes')).toBeInTheDocument()
    expect(within(card('Devices accessing this destination')).getByText('No devices')).toBeInTheDocument()
    expect(await within(card('Recent access')).findByText('No network activity found')).toBeInTheDocument()
  })

  it('shows "Not found" with a way back for an unknown destination', async () => {
    renderDetail({ 'GET /api/destinations/9': reply(404, { detail: 'Destination 9 not found' }) }, '/destinations/9')
    expect(await screen.findByText('Not found')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to destinations' })).toHaveAttribute('href', '/destinations')
  })

  it('shows an error with retry, and recovers', async () => {
    const { api } = renderDetail({ 'GET /api/destinations/2': reply(503, { detail: 'Temporarily unable, please retry' }) })
    expect(await screen.findByText('Unable to load this destination')).toBeInTheDocument()
    api.set('GET /api/destinations/2', destinationDetail())
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    await heading()
  })
})
