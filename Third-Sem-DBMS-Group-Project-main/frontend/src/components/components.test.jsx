import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { installFetch, reply } from '../test/fetchMock.js'
import { historyEvent } from '../test/fixtures.js'
import { EventDrawer } from './EventDrawer.jsx'
import { HealthDots, HealthList } from './HealthIndicators.jsx'
import { HistoryTable } from './HistoryTable.jsx'

const inRouter = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>)

const github = historyEvent()
const unresolved = historyEvent({
  history_id: 102,
  observed_at: '2026-09-19T20:16:40',
  device_identifier: 'PC-LIB-002',
  device_ip: '192.168.30.22',
  node_code: 'LIB-01',
  destination_ip: '192.0.2.77',
  domain: null,
  category: 'UNKNOWN',
})

describe('HistoryTable', () => {
  it('shows every column in the full view', () => {
    render(<HistoryTable items={[github]} />)
    for (const name of ['Time', 'Device', 'IP', 'Node', 'Destination IP', 'Domain', 'Protocol', 'Source port', 'Destination port']) {
      expect(screen.getByRole('columnheader', { name })).toBeInTheDocument()
    }
    const row = screen.getByRole('row', { name: /PC-LAB-A-001/ })
    expect(within(row).getByText(/^19 Sep(t)? 2026, 20:15:32$/)).toBeInTheDocument()
    expect(within(row).getByText('192.168.10.21')).toBeInTheDocument()
    expect(within(row).getByText('LAB-A')).toBeInTheDocument()
    expect(within(row).getByText('203.0.113.20')).toBeInTheDocument()
    expect(within(row).getByText('github.com')).toBeInTheDocument()
  })

  it('shows a dash (not an invented name) when no domain was observed', () => {
    render(<HistoryTable items={[unresolved]} />)
    const row = screen.getByRole('row', { name: /PC-LIB-002/ })
    expect(within(row).getByText('192.0.2.77')).toBeInTheDocument()
    expect(within(row).getAllByText('—')).toHaveLength(4)
  })

  it('shows protocol and ports exactly as observed, without thousands separators', () => {
    render(<HistoryTable items={[historyEvent({ protocol: 'TCP', source_port: 56188, destination_port: 443 })]} />)
    const row = screen.getByRole('row', { name: /PC-LAB-A-001/ })
    expect(within(row).getByText('TCP')).toBeInTheDocument()
    expect(within(row).getByText('56188')).toBeInTheDocument()
    expect(within(row).getByText('443')).toBeInTheDocument()
    expect(within(row).queryByText('—')).not.toBeInTheDocument()
  })

  it('shows a dash for each missing value independently', () => {
    render(<HistoryTable items={[historyEvent({ protocol: 'TCP', source_port: null, destination_port: 443 })]} />)
    const row = screen.getByRole('row', { name: /PC-LAB-A-001/ })
    expect(within(row).getByText('TCP')).toBeInTheDocument()
    expect(within(row).getAllByText('—')).toHaveLength(1)
    expect(within(row).getByText('443')).toBeInTheDocument()
  })

  it('never renders a bogus port', () => {
    render(<HistoryTable items={[historyEvent({ protocol: 'TCP', source_port: '56188', destination_port: NaN })]} />)
    const row = screen.getByRole('row', { name: /PC-LAB-A-001/ })
    expect(within(row).queryByText('56188')).not.toBeInTheDocument()
    expect(within(row).queryByText('NaN')).not.toBeInTheDocument()
  })

  it('marks the source-port column so it can be dropped on narrow screens', () => {
    render(<HistoryTable items={[historyEvent({ protocol: 'TCP', source_port: 56188, destination_port: 443 })]} />)
    expect(screen.getByRole('columnheader', { name: 'Source port' })).toHaveClass('hidden', 'md:table-cell')
    expect(screen.getByRole('columnheader', { name: 'Destination port' })).not.toHaveClass('hidden')
    expect(screen.getByText('56188').closest('td')).toHaveClass('hidden', 'md:table-cell')
  })

  it('adds only the destination port, muted, to the compact view', () => {
    render(<HistoryTable items={[historyEvent({ protocol: 'TCP', source_port: 56188, destination_port: 443 }), unresolved]} variant="compact" />)
    expect(screen.getAllByRole('columnheader').map((th) => th.textContent)).toEqual(['Time', 'Device', 'Node', 'Destination'])
    expect(screen.getByText('443/TCP')).toBeInTheDocument()
    expect(screen.queryByText('56188')).not.toBeInTheDocument()
    expect(screen.getAllByText(/^\d+\/TCP$/)).toHaveLength(1)
  })

  it('has a compact view with only time, device, node and destination', () => {
    render(<HistoryTable items={[github, unresolved]} variant="compact" />)
    expect(screen.getAllByRole('columnheader').map((th) => th.textContent)).toEqual(['Time', 'Device', 'Node', 'Destination'])
    expect(screen.getByText('20:15:32')).toBeInTheDocument()
    expect(screen.getByText('github.com')).toBeInTheDocument()
    expect(screen.getByText('(unresolved)')).toBeInTheDocument()
  })

  it('can hide columns that are redundant on a detail page', () => {
    const { rerender } = render(<HistoryTable items={[github]} hide={['node']} />)
    expect(screen.queryByRole('columnheader', { name: 'Node' })).not.toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Device' })).toBeInTheDocument()

    rerender(<HistoryTable items={[github]} hide={['device']} />)
    expect(screen.queryByRole('columnheader', { name: 'Device' })).not.toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: 'IP' })).not.toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Node' })).toBeInTheDocument()
  })

  it('selects an event by click or keyboard when a handler is given', async () => {
    const onSelect = vi.fn()
    render(<HistoryTable items={[github, unresolved]} onSelect={onSelect} />)
    await userEvent.click(screen.getByRole('row', { name: /PC-LAB-A-001/ }))
    expect(onSelect).toHaveBeenLastCalledWith(github)

    screen.getByRole('row', { name: /PC-LIB-002/ }).focus()
    await userEvent.keyboard('{Enter}')
    expect(onSelect).toHaveBeenLastCalledWith(unresolved)
  })

  it('does not make rows interactive without a handler', () => {
    render(<HistoryTable items={[github]} />)
    expect(screen.getByRole('row', { name: /PC-LAB-A-001/ })).not.toHaveAttribute('tabindex')
  })
})

describe('HealthList', () => {
  const ok = { state: 'ok', data: { status: 'ok', tables: ['a', 'b', 'c', 'd', 'e', 'f'], missing_tables: [] } }

  it('shows both services as operational', () => {
    render(<HealthList health={{ api: { state: 'ok', data: {} }, database: ok }} />)
    expect(screen.getAllByText('Operational')).toHaveLength(2)
    expect(screen.getByText('MySQL connected, 6 of 6 tables present')).toBeInTheDocument()
  })

  it('shows a checking state while loading', () => {
    render(<HealthList health={{ api: { state: 'loading', data: null }, database: { state: 'loading', data: null } }} />)
    expect(screen.getAllByText('Checking')).toHaveLength(2)
  })

  it('names the missing tables when the schema is incomplete', () => {
    const database = { state: 'error', data: { status: 'error', database: 'connected', tables: ['users'], missing_tables: ['nodes', 'devices'] } }
    render(<HealthList health={{ api: { state: 'ok', data: {} }, database }} />)
    expect(screen.getByText('Missing tables: nodes, devices')).toBeInTheDocument()
    expect(screen.getByText('Unavailable')).toBeInTheDocument()
  })

  it('explains an unreachable database and API', () => {
    const health = {
      api: { state: 'error', data: null, error: new Error('The server is unavailable.') },
      database: { state: 'error', data: null },
    }
    render(<HealthList health={health} />)
    expect(screen.getByText('The server is unavailable.')).toBeInTheDocument()
    expect(screen.getByText('MySQL is unreachable or the schema is missing')).toBeInTheDocument()
    expect(screen.getAllByText('Unavailable')).toHaveLength(2)
  })
})

describe('HealthDots', () => {
  it('summarises API and database status for the sidebar', () => {
    render(<HealthDots health={{ api: { state: 'ok' }, database: { state: 'error' } }} />)
    const status = screen.getByRole('status', { name: 'System health' })
    expect(within(status).getByText('API')).toHaveAttribute('title', 'API: operational')
    expect(within(status).getByText('Database')).toHaveAttribute('title', 'Database: unavailable')
  })
})

describe('EventDrawer', () => {
  it('loads and shows the event with links to the related pages', async () => {
    const api = installFetch({ 'GET /api/history/101': github })
    const onClose = vi.fn()
    inRouter(<EventDrawer eventId={101} onClose={onClose} />)

    expect(screen.getByRole('dialog', { name: 'Event #101' })).toBeInTheDocument()
    expect(await screen.findByText(/^19 Sep(t)? 2026, 20:15:32$/)).toBeInTheDocument()
    expect(api.callsTo('GET /api/history/101')).toHaveLength(1)

    expect(screen.getByRole('link', { name: 'PC-LAB-A-001' })).toHaveAttribute('href', '/devices/1')
    expect(screen.getByRole('link', { name: 'Computer Lab A' })).toHaveAttribute('href', '/nodes/1')
    expect(screen.getByRole('link', { name: 'github.com' })).toHaveAttribute('href', '/destinations/2')
    expect(screen.getByRole('link', { name: '203.0.113.20' })).toHaveAttribute('href', '/destinations/2')
    expect(screen.getByText('Development')).toBeInTheDocument()
    expect(screen.getByText(/not a security classification/)).toBeInTheDocument()
  })

  it('says so when no domain was observed', async () => {
    installFetch({ 'GET /api/history/102': unresolved })
    inRouter(<EventDrawer eventId={102} onClose={() => {}} />)
    expect(await screen.findByText('Not observed')).toBeInTheDocument()
  })

  it('shows a loading state first', async () => {
    let release
    installFetch({ 'GET /api/history/101': () => new Promise((resolve) => (release = () => resolve(github))) })
    inRouter(<EventDrawer eventId={101} onClose={() => {}} />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
    release()
    await screen.findByText('PC-LAB-A-001', { selector: 'a' })
  })

  it('reports an event that does not exist as not found', async () => {
    installFetch({ 'GET /api/history/999': reply(404, { detail: 'History event 999 not found' }) })
    inRouter(<EventDrawer eventId={999} onClose={() => {}} />)
    expect(await screen.findByText('Not found')).toBeInTheDocument()
    expect(screen.getByText('History event 999 not found')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
  })

  it('offers a retry after a server error, and recovers', async () => {
    const api = installFetch({ 'GET /api/history/101': reply(500, { detail: 'Internal server error' }) })
    inRouter(<EventDrawer eventId={101} onClose={() => {}} />)
    expect(await screen.findByText('Unable to load this event')).toBeInTheDocument()

    api.set('GET /api/history/101', github)
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('link', { name: 'PC-LAB-A-001' })).toBeInTheDocument()
  })

  it('closes from the close button, and when a link inside it is followed', async () => {
    installFetch({ 'GET /api/history/101': github })
    const onClose = vi.fn()
    inRouter(<EventDrawer eventId={101} onClose={onClose} />)
    const link = await screen.findByRole('link', { name: 'PC-LAB-A-001' })

    await userEvent.click(link)
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1))
    await userEvent.click(screen.getByRole('button', { name: 'Close panel' }))
    expect(onClose).toHaveBeenCalledTimes(2)
  })
})
