import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { networkFailure, reply } from '../test/fetchMock.js'
import { ADMIN, ANALYST } from '../test/fixtures.js'
import { SESSION_KEY, allPageRoutes, renderApp } from '../test/render.jsx'

const LOGIN_OK = { access_token: 'issued-token', token_type: 'bearer', expires_in: 3600, user: ADMIN }

const signInAs = async (user, email = 'admin@netmonitor.local', password = 'Admin@12345') => {
  await user.type(screen.getByLabelText('Email'), email)
  await user.type(screen.getByLabelText('Password'), password)
  await user.click(screen.getByRole('button', { name: 'Sign in' }))
}

describe('LoginPage', () => {
  it('shows the sign-in form and names the browser tab', () => {
    renderApp('/login', { user: null })
    expect(screen.getByRole('heading', { name: 'NetMonitor' })).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'password')
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
    expect(document.title).toBe('Sign in · NetMonitor')
  })

  it('asks for both fields without contacting the server', async () => {
    const { api } = renderApp('/login', { user: null })
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Enter your email and password.')
    expect(api.callsTo('POST /api/auth/login')).toHaveLength(0)
  })

  it('signs in and lands on the dashboard', async () => {
    const { api } = renderApp('/login', { user: null, routes: { 'POST /api/auth/login': LOGIN_OK, ...allPageRoutes() } })
    const user = userEvent.setup()
    await signInAs(user, '  admin@netmonitor.local  ')

    expect(await screen.findByRole('heading', { level: 1, name: 'Dashboard' })).toBeInTheDocument()
    expect(api.lastCall('POST /api/auth/login').body).toEqual({ email: 'admin@netmonitor.local', password: 'Admin@12345' })
    expect(api.lastCall('GET /api/dashboard/summary').headers.authorization).toBe('Bearer issued-token')
    expect(JSON.parse(localStorage.getItem(SESSION_KEY)).token).toBe('issued-token')
  })

  it('returns the user to the page they originally asked for', async () => {
    renderApp('/nodes', { user: null, routes: { 'POST /api/auth/login': LOGIN_OK, ...allPageRoutes() } })
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument()
    await signInAs(userEvent.setup())
    expect(await screen.findByRole('heading', { level: 1, name: 'Nodes' })).toBeInTheDocument()
  })

  it('shows the server message for wrong credentials and lets the user retry', async () => {
    const { api } = renderApp('/login', { user: null, routes: { 'POST /api/auth/login': reply(401, { detail: 'Invalid email or password' }) } })
    const user = userEvent.setup()
    await signInAs(user, 'admin@netmonitor.local', 'wrong-password')

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password')
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeEnabled()
    expect(screen.getByLabelText('Email')).toHaveValue('admin@netmonitor.local')
    expect(localStorage.getItem(SESSION_KEY)).toBeNull()
    expect(screen.queryByText('Your session has ended. Please sign in again.')).not.toBeInTheDocument()

    api.set('POST /api/auth/login', LOGIN_OK)
    api.set('GET /api/dashboard/summary', allPageRoutes()['GET /api/dashboard/summary'])
    Object.entries(allPageRoutes()).forEach(([key, value]) => api.set(key, value))
    await user.clear(screen.getByLabelText('Password'))
    await user.type(screen.getByLabelText('Password'), 'Admin@12345')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Dashboard' })).toBeInTheDocument()
  })

  it('tells the user when the server cannot be reached', async () => {
    renderApp('/login', { user: null, routes: { 'POST /api/auth/login': () => networkFailure() } })
    await signInAs(userEvent.setup())
    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to reach the server')
  })

  it('reports a disabled account', async () => {
    renderApp('/login', { user: null, routes: { 'POST /api/auth/login': reply(403, { detail: 'This account is disabled' }) } })
    await signInAs(userEvent.setup())
    expect(await screen.findByRole('alert')).toHaveTextContent('This account is disabled')
  })

  it('disables the button while the request is running', async () => {
    let release
    renderApp('/login', {
      user: null,
      routes: { 'POST /api/auth/login': () => new Promise((resolve) => (release = () => resolve(reply(401, { detail: 'Invalid email or password' })))) },
    })
    await signInAs(userEvent.setup())
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeDisabled()
    release()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Sign in' })).toBeEnabled())
  })

  it('sends someone who is already signed in straight to the dashboard', async () => {
    renderApp('/login', { user: ADMIN, routes: allPageRoutes() })
    expect(await screen.findByRole('heading', { level: 1, name: 'Dashboard' })).toBeInTheDocument()
  })

  it('explains that the session ended when a stored token is rejected', async () => {
    renderApp('/nodes', { user: ANALYST, routes: { 'GET /api/auth/me': reply(401, { detail: 'Invalid or expired token' }) } })
    expect(await screen.findByText('Your session has ended. Please sign in again.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('offers one-click demo accounts in development builds only', async () => {
    renderApp('/login', { user: null })
    const user = userEvent.setup()
    expect(screen.getByText('Demo accounts (development build)')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Analyst/ }))
    expect(screen.getByLabelText('Email')).toHaveValue('analyst@netmonitor.local')
    expect(screen.getByLabelText('Password')).toHaveValue('Analyst@12345')
  })
})
