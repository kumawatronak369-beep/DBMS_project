import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { installFetch, networkFailure, reply } from '../test/fetchMock.js'
import { ADMIN, ANALYST } from '../test/fixtures.js'
import { SESSION_KEY, seedSession } from '../test/render.jsx'
import { AuthProvider } from './AuthProvider.jsx'
import { useAuth } from './useAuth.js'

function Probe() {
  const auth = useAuth()
  const [loginError, setLoginError] = useState('')
  return (
    <div>
      <p data-testid="state">
        {auth.checking ? 'checking' : auth.isAuthenticated ? 'signed-in' : 'signed-out'}
      </p>
      <p data-testid="user">{auth.user?.email ?? 'nobody'}</p>
      <p data-testid="name">{auth.user?.name ?? '-'}</p>
      <p data-testid="admin">{String(auth.isAdmin)}</p>
      <p data-testid="expired">{String(auth.sessionExpired)}</p>
      <p data-testid="login-error">{loginError}</p>
      <button onClick={() => auth.login('admin@netmonitor.local', 'Admin@12345').catch((e) => setLoginError(e.message))}>
        do login
      </button>
      <button onClick={() => auth.login('admin@netmonitor.local', 'wrong').catch((e) => setLoginError(e.message))}>
        do bad login
      </button>
      <button onClick={() => auth.logout()}>do logout</button>
    </div>
  )
}

const renderProbe = () =>
  render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  )

const LOGIN_OK = { access_token: 'issued-token', token_type: 'bearer', expires_in: 3600, user: ADMIN }
const stored = () => JSON.parse(localStorage.getItem(SESSION_KEY))

describe('AuthProvider: starting up', () => {
  it('starts signed out when there is no stored session (and makes no request)', () => {
    const api = installFetch()
    renderProbe()
    expect(screen.getByTestId('state')).toHaveTextContent('signed-out')
    expect(api.calls).toHaveLength(0)
  })

  it('confirms a stored session with the server and refreshes the user (new role/name)', async () => {
    seedSession({ ...ADMIN, name: 'Old Name' }, { token: 'stored-token' })
    const api = installFetch({ 'GET /api/auth/me': { ...ADMIN, name: 'Fresh Name' } })
    renderProbe()
    expect(screen.getByTestId('state')).toHaveTextContent('checking')

    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('signed-in'))
    expect(screen.getByTestId('name')).toHaveTextContent('Fresh Name')
    expect(api.lastCall('GET /api/auth/me').headers.authorization).toBe('Bearer stored-token')
    expect(stored().user.name).toBe('Fresh Name')
  })

  it('ignores an expired stored session', () => {
    seedSession(ADMIN, { expiresInMs: -1000 })
    const api = installFetch()
    renderProbe()
    expect(screen.getByTestId('state')).toHaveTextContent('signed-out')
    expect(api.calls).toHaveLength(0)
  })

  it('survives a corrupted stored session', () => {
    localStorage.setItem(SESSION_KEY, '{not json')
    installFetch()
    renderProbe()
    expect(screen.getByTestId('state')).toHaveTextContent('signed-out')
  })

  it('signs out (and reports an expired session) when the server rejects the stored token', async () => {
    seedSession(ADMIN)
    installFetch({ 'GET /api/auth/me': reply(401, { detail: 'Invalid or expired token' }) })
    renderProbe()
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('signed-out'))
    expect(screen.getByTestId('expired')).toHaveTextContent('true')
    expect(localStorage.getItem(SESSION_KEY)).toBeNull()
  })

  it('keeps the session when the server is merely unreachable', async () => {
    seedSession(ADMIN)
    installFetch({ 'GET /api/auth/me': () => networkFailure() })
    renderProbe()
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('signed-in'))
    expect(localStorage.getItem(SESSION_KEY)).not.toBeNull()
  })
})

describe('AuthProvider: login and logout', () => {
  it('logs in, stores the session and uses the token afterwards', async () => {
    const api = installFetch({ 'POST /api/auth/login': LOGIN_OK, 'POST /api/auth/logout': reply(204) })
    const before = Date.now()
    renderProbe()
    await userEvent.click(screen.getByRole('button', { name: 'do login' }))

    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('signed-in'))
    expect(screen.getByTestId('user')).toHaveTextContent('admin@netmonitor.local')
    expect(screen.getByTestId('admin')).toHaveTextContent('true')
    expect(api.lastCall('POST /api/auth/login').body).toEqual({ email: 'admin@netmonitor.local', password: 'Admin@12345' })

    const session = stored()
    expect(session.token).toBe('issued-token')
    expect(session.expiresAt).toBeGreaterThanOrEqual(before + 3600 * 1000)
    expect(JSON.stringify(session)).not.toContain('Admin@12345')

    await userEvent.click(screen.getByRole('button', { name: 'do logout' }))
    expect(api.lastCall('POST /api/auth/logout').headers.authorization).toBe('Bearer issued-token')
  })

  it('does not treat an analyst as an admin', async () => {
    installFetch({ 'POST /api/auth/login': { ...LOGIN_OK, user: ANALYST } })
    renderProbe()
    await userEvent.click(screen.getByRole('button', { name: 'do login' }))
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('signed-in'))
    expect(screen.getByTestId('admin')).toHaveTextContent('false')
  })

  it('rejects a bad login with the server message and stores nothing', async () => {
    installFetch({ 'POST /api/auth/login': reply(401, { detail: 'Invalid email or password' }) })
    renderProbe()
    await userEvent.click(screen.getByRole('button', { name: 'do bad login' }))
    await waitFor(() => expect(screen.getByTestId('login-error')).toHaveTextContent('Invalid email or password'))
    expect(screen.getByTestId('state')).toHaveTextContent('signed-out')
    expect(screen.getByTestId('expired')).toHaveTextContent('false')
    expect(localStorage.getItem(SESSION_KEY)).toBeNull()
  })

  it('logs out: clears the session, even if the server cannot be reached', async () => {
    seedSession(ADMIN)
    installFetch({ 'GET /api/auth/me': ADMIN, 'POST /api/auth/logout': () => networkFailure() })
    renderProbe()
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('signed-in'))

    await userEvent.click(screen.getByRole('button', { name: 'do logout' }))
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('signed-out'))
    expect(localStorage.getItem(SESSION_KEY)).toBeNull()
  })

  it('still works in memory when browser storage is unavailable', async () => {
    installFetch({ 'POST /api/auth/login': LOGIN_OK })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('storage disabled')
    })
    renderProbe()
    await userEvent.click(screen.getByRole('button', { name: 'do login' }))
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('signed-in'))
  })
})
