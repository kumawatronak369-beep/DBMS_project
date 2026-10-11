import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { AuthProvider } from '../hooks/AuthProvider.jsx'
import { installFetch, reply } from '../test/fetchMock.js'
import { ADMIN, ANALYST } from '../test/fixtures.js'
import { baseRoutes, seedSession } from '../test/render.jsx'
import { RequireAdmin, RequireAuth } from './guards.jsx'

function LoginProbe() {
  const location = useLocation()
  return <p>login page (came from {location.state?.from?.pathname ?? 'nowhere'})</p>
}

function renderGuarded(route, { user = null, routes = {} } = {}) {
  installFetch({ ...(user ? baseRoutes(user) : {}), ...routes })
  if (user) seedSession(user)
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginProbe />} />
          <Route element={<RequireAuth />}>
            <Route path="/private" element={<p>private area</p>} />
            <Route element={<RequireAdmin />}>
              <Route path="/admin" element={<p>admin area</p>} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('RequireAuth', () => {
  it('sends a signed-out visitor to the login page and remembers where they were going', () => {
    renderGuarded('/private')
    expect(screen.getByText('login page (came from /private)')).toBeInTheDocument()
    expect(screen.queryByText('private area')).not.toBeInTheDocument()
  })

  it('lets a signed-in user through', async () => {
    renderGuarded('/private', { user: ANALYST })
    expect(await screen.findByText('private area')).toBeInTheDocument()
  })

  it('shows a loading indicator (not the page, not the login) while the session is being confirmed', async () => {
    let release
    const gate = new Promise((resolve) => {
      release = resolve
    })
    renderGuarded('/private', { user: ANALYST, routes: { 'GET /api/auth/me': () => gate.then(() => ANALYST) } })
    expect(screen.getByRole('status', { name: 'Checking your session' })).toBeInTheDocument()
    expect(screen.queryByText('private area')).not.toBeInTheDocument()
    expect(screen.queryByText(/login page/)).not.toBeInTheDocument()

    release()
    expect(await screen.findByText('private area')).toBeInTheDocument()
  })

  it('sends the user to login when the server says the stored token is no longer valid', async () => {
    renderGuarded('/private', {
      user: ADMIN,
      routes: { 'GET /api/auth/me': reply(401, { detail: 'Invalid or expired token' }) },
    })
    expect(await screen.findByText(/login page/)).toBeInTheDocument()
    expect(screen.queryByText('private area')).not.toBeInTheDocument()
  })
})

describe('RequireAdmin', () => {
  it('shows an admin the admin page', async () => {
    renderGuarded('/admin', { user: ADMIN })
    expect(await screen.findByText('admin area')).toBeInTheDocument()
  })

  it('tells an analyst the page is for administrators only, and offers a way back', async () => {
    renderGuarded('/admin', { user: ANALYST })
    expect(await screen.findByText('Administrators only')).toBeInTheDocument()
    expect(screen.getByText('Your account does not have permission to view this page.')).toBeInTheDocument()
    expect(screen.queryByText('admin area')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to dashboard' })).toHaveAttribute('href', '/dashboard')
  })

  it('still requires a login first', () => {
    renderGuarded('/admin')
    expect(screen.getByText('login page (came from /admin)')).toBeInTheDocument()
  })

  it('reacts to the role the server reports, not the stored one', async () => {
    seedSession(ADMIN)
    installFetch({ ...baseRoutes(ANALYST) })
    render(
      <MemoryRouter initialEntries={['/admin']}>
        <AuthProvider>
          <Routes>
            <Route element={<RequireAuth />}>
              <Route element={<RequireAdmin />}>
                <Route path="/admin" element={<p>admin area</p>} />
              </Route>
            </Route>
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    )
    await waitFor(() => expect(screen.getByText('Administrators only')).toBeInTheDocument())
  })
})
