import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../services/api.js'
import { DataState, EmptyState, ErrorState, Skeleton, SkeletonBlock, SkeletonRows } from './States.jsx'

const inRouter = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>)
const networkError = () => new ApiError('Unable to reach the server. Check your connection and try again.', 0)
const httpError = (status, message) => new ApiError(message, status)

describe('loading skeletons', () => {
  it('SkeletonRows announces itself as loading and draws the requested rows', () => {
    const { container } = render(<SkeletonRows rows={4} />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
    expect(container.querySelectorAll('.nm-skeleton')).toHaveLength(4)
  })
  it('SkeletonBlock has the requested height', () => {
    const { container } = render(<SkeletonBlock height={123} />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
    expect(container.querySelector('.nm-skeleton')).toHaveStyle({ height: '123px' })
  })
  it('Skeleton is hidden from assistive technology', () => {
    const { container } = render(<Skeleton className="h-4" />)
    expect(container.firstChild).toHaveAttribute('aria-hidden', 'true')
  })
})

describe('EmptyState', () => {
  it('shows a title and hint, and an optional action', () => {
    render(<EmptyState title="No network activity found" hint="Try changing your filters." action={<button>Clear</button>} />)
    expect(screen.getByText('No network activity found')).toBeInTheDocument()
    expect(screen.getByText('Try changing your filters.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Clear' })).toBeInTheDocument()
  })
  it('has sensible defaults', () => {
    render(<EmptyState />)
    expect(screen.getByText('Nothing to show')).toBeInTheDocument()
  })
})

describe('ErrorState', () => {
  it('shows the message and retries on request', async () => {
    const onRetry = vi.fn()
    render(<ErrorState error={httpError(500, 'The server ran into a problem. Please try again.')} onRetry={onRetry} />)
    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByText('Unable to load this data')).toBeInTheDocument()
    expect(screen.getByText('The server ran into a problem. Please try again.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('uses a caller-supplied title for ordinary failures', () => {
    render(<ErrorState error={httpError(500, 'x')} title="Unable to load network history" onRetry={() => {}} />)
    expect(screen.getByText('Unable to load network history')).toBeInTheDocument()
  })

  it('explains an unreachable server', () => {
    render(<ErrorState error={networkError()} onRetry={() => {}} />)
    expect(screen.getByText("Can't reach the server")).toBeInTheDocument()
    expect(screen.getByText(/Unable to reach the server/)).toBeInTheDocument()
  })

  it('explains a permission problem', () => {
    render(<ErrorState error={httpError(403, 'You do not have permission to do that.')} onRetry={() => {}} />)
    expect(screen.getByText('Not permitted')).toBeInTheDocument()
  })

  it('treats a 404 as final: "Not found", no retry, and a way back', () => {
    inRouter(
      <ErrorState
        error={httpError(404, 'Node 9 not found')}
        title="Unable to load this node"
        onRetry={() => {}}
        backTo={{ to: '/nodes', label: 'Back to nodes' }}
      />,
    )
    expect(screen.getByText('Not found')).toBeInTheDocument()
    expect(screen.queryByText('Unable to load this node')).not.toBeInTheDocument()
    expect(screen.getByText('Node 9 not found')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to nodes' })).toHaveAttribute('href', '/nodes')
  })

  it('offers both retry and a way back for other failures', () => {
    inRouter(<ErrorState error={httpError(500, 'x')} onRetry={() => {}} backTo={{ to: '/nodes', label: 'Back to nodes' }} />)
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to nodes' })).toBeInTheDocument()
  })

  it('copes with a missing error object', () => {
    render(<ErrorState />)
    expect(screen.getByText('Something went wrong. Please try again.')).toBeInTheDocument()
  })
})

describe('DataState', () => {
  const state = (overrides = {}) => ({ data: null, error: null, loading: false, reload: vi.fn(), ...overrides })
  const renderState = (result, props = {}) =>
    inRouter(
      <DataState result={result} {...props}>
        {(data) => <p>data: {data.value}</p>}
      </DataState>,
    )

  it('shows a skeleton while nothing has loaded', () => {
    renderState(state({ loading: true }))
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
  })

  it('shows a custom skeleton when given one', () => {
    renderState(state({ loading: true }), { skeleton: <p>custom skeleton</p> })
    expect(screen.getByText('custom skeleton')).toBeInTheDocument()
  })

  it('shows an error with retry when the first load fails, and retry reloads', async () => {
    const result = state({ error: httpError(500, 'boom') })
    renderState(result, { errorTitle: 'Unable to load nodes' })
    expect(screen.getByText('Unable to load nodes')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(result.reload).toHaveBeenCalledTimes(1)
  })

  it('shows the not-found state (with a way back) for a 404', () => {
    renderState(state({ error: httpError(404, 'Node 9 not found') }), { backTo: { to: '/nodes', label: 'Back to nodes' } })
    expect(screen.getByText('Not found')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to nodes' })).toBeInTheDocument()
  })

  it('shows the empty state when there is nothing to list', () => {
    renderState(state({ data: { value: 'x', items: [] } }), {
      isEmpty: (data) => data.items.length === 0,
      empty: { title: 'No nodes registered yet', hint: 'Add a node to start monitoring.' },
    })
    expect(screen.getByText('No nodes registered yet')).toBeInTheDocument()
    expect(screen.getByText('Add a node to start monitoring.')).toBeInTheDocument()
    expect(screen.queryByText(/data:/)).not.toBeInTheDocument()
  })

  it('renders the data', () => {
    renderState(state({ data: { value: 42 } }))
    expect(screen.getByText('data: 42')).toBeInTheDocument()
  })

  it('dims the data while a refresh is in flight', () => {
    const { container } = renderState(state({ data: { value: 1 }, loading: true }))
    expect(container.firstChild).toHaveClass('opacity-70')
  })

  it('keeps showing the data and adds a notice when a refresh fails', async () => {
    const result = state({ data: { value: 1 }, error: httpError(503, 'The server is unavailable.') })
    renderState(result)
    expect(screen.getByText('data: 1')).toBeInTheDocument()
    expect(screen.getByText('Could not refresh: The server is unavailable.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(result.reload).toHaveBeenCalledTimes(1)
  })

  it('can suppress the per-card notice (the page shows one combined notice)', () => {
    renderState(state({ data: { value: 1 }, error: httpError(503, 'down') }), { quiet: true })
    expect(screen.getByText('data: 1')).toBeInTheDocument()
    expect(screen.queryByText(/Could not refresh/)).not.toBeInTheDocument()
  })

  it('shows the notice above the empty state too', () => {
    renderState(state({ data: { items: [] }, error: httpError(503, 'down') }), {
      isEmpty: () => true,
      empty: { title: 'Nothing here' },
    })
    expect(screen.getByText('Nothing here')).toBeInTheDocument()
    expect(screen.getByText('Could not refresh: down')).toBeInTheDocument()
  })
})
