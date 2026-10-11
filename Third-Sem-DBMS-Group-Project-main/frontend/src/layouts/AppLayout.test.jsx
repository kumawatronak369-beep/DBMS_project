import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { reply } from '../test/fetchMock.js'
import { ADMIN, ANALYST } from '../test/fixtures.js'
import { SESSION_KEY, allPageRoutes, renderApp } from '../test/render.jsx'

const ready = async (user = ADMIN) => {
  const view = renderApp('/dashboard', { user, routes: allPageRoutes() })
  await screen.findByRole('heading', { level: 1, name: 'Dashboard' })
  return view
}

describe('AppLayout', () => {
  it('lists the main pages, plus Users for admins', async () => {
    await ready(ADMIN)
    const nav = screen.getByRole('navigation', { name: 'Main navigation' })
    for (const name of ['Dashboard', 'Nodes', 'Devices', 'Destinations', 'Network History', 'Reports', 'Users', 'Settings']) {
      expect(within(nav).getByRole('link', { name })).toBeInTheDocument()
    }
  })

  it('does not list Users for analysts', async () => {
    await ready(ANALYST)
    const nav = screen.getByRole('navigation', { name: 'Main navigation' })
    expect(within(nav).queryByRole('link', { name: 'Users' })).not.toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: 'Settings' })).toBeInTheDocument()
  })

  it('marks the current page in the sidebar', async () => {
    await ready()
    const nav = screen.getByRole('navigation', { name: 'Main navigation' })
    expect(within(nav).getByRole('link', { name: 'Dashboard' })).toHaveAttribute('aria-current', 'page')
    expect(within(nav).getByRole('link', { name: 'Nodes' })).not.toHaveAttribute('aria-current')
  })

  it('always says the data is simulated (full text on wide screens, short text on phones)', async () => {
    await ready()
    const badge = screen.getByTitle('Network events in this environment are generated for demonstration')
    expect(within(badge).getByText('Simulated demo data')).toBeInTheDocument()
    expect(within(badge).getByText('Demo data')).toBeInTheDocument()
  })

  it('shows API and database health in the sidebar', async () => {
    await ready()
    await waitFor(() => {
      const health = screen.getByRole('status', { name: 'System health' })
      expect(within(health).getByText('API')).toHaveAttribute('title', 'API: operational')
      expect(within(health).getByText('Database')).toHaveAttribute('title', 'Database: operational')
    })
  })

  it('shows a red database indicator when the database check fails', async () => {
    renderApp('/dashboard', {
      routes: allPageRoutes({ 'GET /api/health/db': reply(503, { status: 'error', database: 'unreachable', tables: [], missing_tables: [] }) }),
    })
    await screen.findByRole('heading', { level: 1, name: 'Dashboard' })
    await waitFor(() => {
      const health = screen.getByRole('status', { name: 'System health' })
      expect(within(health).getByText('Database')).toHaveAttribute('title', 'Database: unavailable')
    })
  })
})

describe('user menu', () => {
  it('shows who is signed in, with a link to settings and a sign-out', async () => {
    await ready(ANALYST)
    const user = userEvent.setup()
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Network Analyst/ }))
    const menu = screen.getByRole('menu')
    expect(within(menu).getByText('analyst@netmonitor.local')).toBeInTheDocument()
    expect(within(menu).getByRole('menuitem', { name: 'Settings' })).toHaveAttribute('href', '/settings')
    expect(within(menu).getByRole('menuitem', { name: 'Sign out' })).toBeInTheDocument()
  })

  it('closes on Escape and on a click elsewhere', async () => {
    await ready()
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /System Administrator/ }))
    expect(screen.getByRole('menu')).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /System Administrator/ }))
    await user.click(screen.getByRole('heading', { level: 1, name: 'Dashboard' }))
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })

  it('signs out: ends the session and returns to the login page', async () => {
    const { api } = await ready()
    api.set('POST /api/auth/logout', reply(204))
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /System Administrator/ }))
    await user.click(screen.getByRole('menuitem', { name: 'Sign out' }))

    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument()
    expect(localStorage.getItem(SESSION_KEY)).toBeNull()
    expect(api.callsTo('POST /api/auth/logout')).toHaveLength(1)
    expect(screen.queryByText('Your session has ended. Please sign in again.')).not.toBeInTheDocument()
  })
})

describe('mobile navigation drawer', () => {
  it('opens from the menu button and closes with its close button', async () => {
    await ready()
    const user = userEvent.setup()
    expect(screen.getAllByRole('navigation', { name: 'Main navigation' })).toHaveLength(1)

    await user.click(screen.getByRole('button', { name: 'Open navigation' }))
    expect(screen.getAllByRole('navigation', { name: 'Main navigation' })).toHaveLength(2)
    await user.click(screen.getByRole('button', { name: 'Close navigation' }))
    expect(screen.getAllByRole('navigation', { name: 'Main navigation' })).toHaveLength(1)
  })

  it('closes when the user picks a page', async () => {
    await ready()
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Open navigation' }))
    const [, drawer] = screen.getAllByRole('navigation', { name: 'Main navigation' })
    await user.click(within(drawer).getByRole('link', { name: 'Nodes' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Nodes' })).toBeInTheDocument()
    expect(screen.getAllByRole('navigation', { name: 'Main navigation' })).toHaveLength(1)
    expect(screen.queryByRole('button', { name: 'Close navigation' })).not.toBeInTheDocument()
  })
})
