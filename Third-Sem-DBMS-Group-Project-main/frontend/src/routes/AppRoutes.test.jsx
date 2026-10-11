import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { reply } from '../test/fetchMock.js'
import { ADMIN, ANALYST, paginated } from '../test/fixtures.js'
import { allPageRoutes, renderApp } from '../test/render.jsx'

const heading = (name) => screen.findByRole('heading', { level: 1, name })
const sidebar = () => screen.getByRole('navigation', { name: 'Main navigation' })

describe('routing', () => {
  it('opens the dashboard at the site root', async () => {
    renderApp('/', { routes: allPageRoutes() })
    expect(await heading('Dashboard')).toBeInTheDocument()
    expect(document.title).toBe('Dashboard · NetMonitor')
  })

  it('sends a signed-out visitor to the login page from any protected address', async () => {
    for (const path of ['/dashboard', '/nodes', '/nodes/1', '/history', '/reports', '/settings', '/users', '/nowhere']) {
      const { unmount } = renderApp(path, { user: null })
      expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument()
      unmount()
    }
  })

  it('shows a page-not-found screen with a way home for unknown addresses', async () => {
    renderApp('/does-not-exist', { routes: allPageRoutes() })
    expect(await screen.findByText('Page not found')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to dashboard' })).toHaveAttribute('href', '/dashboard')
    expect(document.title).toBe('Page not found · NetMonitor')
    expect(sidebar()).toBeInTheDocument()
  })

  it('moves between pages using the sidebar', async () => {
    renderApp('/dashboard', { routes: allPageRoutes() })
    const user = userEvent.setup()
    await heading('Dashboard')

    const visits = [
      ['Nodes', 'Nodes'],
      ['Devices', 'Devices'],
      ['Destinations', 'Destinations'],
      ['Network History', 'Network history'],
      ['Reports', 'Reports'],
      ['Dashboard', 'Dashboard'],
    ]
    for (const [link, title] of visits) {
      await user.click(within(sidebar()).getByRole('link', { name: link }))
      expect(await heading(title)).toBeInTheDocument()
      expect(within(sidebar()).getByRole('link', { name: link })).toHaveAttribute('aria-current', 'page')
    }
  })

  it('opens the settings page from the sidebar', async () => {
    renderApp('/dashboard', { routes: allPageRoutes() })
    await heading('Dashboard')
    await userEvent.click(within(sidebar()).getByRole('link', { name: 'Settings' }))
    expect(await heading('Settings')).toBeInTheDocument()
  })

  it('lets an admin open user management', async () => {
    renderApp('/dashboard', { user: ADMIN, routes: allPageRoutes({ 'GET /api/users': paginated([ADMIN, ANALYST]) }) })
    await heading('Dashboard')
    await userEvent.click(within(sidebar()).getByRole('link', { name: 'Users' }))
    expect(await heading('Users')).toBeInTheDocument()
    expect(await screen.findByText('analyst@netmonitor.local')).toBeInTheDocument()
  })

  it('hides user management from an analyst and blocks the address', async () => {
    renderApp('/dashboard', { user: ANALYST, routes: allPageRoutes() })
    await heading('Dashboard')
    expect(within(sidebar()).queryByRole('link', { name: 'Users' })).not.toBeInTheDocument()
  })

  it('shows an analyst who types the users address "Administrators only", without asking the API', async () => {
    const { api } = renderApp('/users', { user: ANALYST, routes: allPageRoutes() })
    expect(await screen.findByText('Administrators only')).toBeInTheDocument()
    expect(api.callsTo('GET /api/users')).toHaveLength(0)
  })

  it('ends up on the login page when the session is rejected mid-use', async () => {
    const { api } = renderApp('/nodes', { routes: allPageRoutes() })
    await heading('Nodes')
    api.set('GET /api/dashboard/summary', reply(401, { detail: 'Invalid or expired token' }))
    await userEvent.click(within(sidebar()).getByRole('link', { name: 'Dashboard' }))

    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByText('Your session has ended. Please sign in again.')).toBeInTheDocument()
  })
})
