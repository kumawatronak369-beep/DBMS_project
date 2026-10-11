import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { reply } from '../test/fetchMock.js'
import { ADMIN, ANALYST, paginated } from '../test/fixtures.js'
import { renderApp } from '../test/render.jsx'

const DISABLED = { ...ANALYST, user_id: 3, name: 'Old Analyst', email: 'old@netmonitor.local', status: 'DISABLED' }
const renderUsers = ({ routes = {}, route = '/users', user = ADMIN } = {}) =>
  renderApp(route, { user, routes: { 'GET /api/users': paginated([ADMIN, ANALYST, DISABLED]), ...routes } })
const ready = () => screen.findByRole('row', { name: /Network Analyst/ })

describe('UsersPage', () => {
  it('lists users with role, status and last login', async () => {
    renderUsers()
    await ready()
    const admin = screen.getByRole('row', { name: /System Administrator/ })
    expect(within(admin).getByText('(you)')).toBeInTheDocument()
    expect(within(admin).getByText('admin@netmonitor.local')).toBeInTheDocument()
    expect(within(screen.getByRole('row', { name: /Network Analyst/ })).getByText('Never')).toBeInTheDocument()
    expect(within(screen.getByRole('row', { name: /Old Analyst/ })).getByText('Disabled')).toBeInTheDocument()
  })

  it('never renders a password hash even if one were sent', async () => {
    renderUsers({ routes: { 'GET /api/users': paginated([{ ...ANALYST, password_hash: 'SECRET-HASH' }]) } })
    await ready()
    expect(document.body.textContent).not.toContain('SECRET-HASH')
  })

  it('does not let you disable your own account', async () => {
    renderUsers()
    await ready()
    expect(screen.getByRole('button', { name: 'You cannot disable your own account' })).toBeDisabled()
  })

  it('searches and filters on the backend', async () => {
    const { api } = renderUsers()
    await ready()
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search users' }), 'analyst')
    await waitFor(() => expect(api.lastCall('GET /api/users').query.search).toBe('analyst'))
    await userEvent.selectOptions(screen.getByLabelText('Filter by role'), 'ADMIN')
    await userEvent.selectOptions(screen.getByLabelText('Filter by status'), 'DISABLED')
    await waitFor(() => expect(api.lastCall('GET /api/users').query).toMatchObject({ role: 'ADMIN', status: 'DISABLED' }))
  })

  it('has filtered-empty and error states', async () => {
    const { unmount } = renderUsers({ route: '/users?role=ADMIN', routes: { 'GET /api/users': paginated([]) } })
    expect(await screen.findByText('No users match your filters')).toBeInTheDocument()
    unmount()
    const { api } = renderUsers({ routes: { 'GET /api/users': reply(500, { detail: 'Internal server error' }) } })
    expect(await screen.findByText('Unable to load users')).toBeInTheDocument()
    api.set('GET /api/users', paginated([ANALYST]))
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    await ready()
  })

  it('adds a user after validating the form', async () => {
    const { api } = renderUsers({ routes: { 'POST /api/users': { ...ANALYST, user_id: 9 } } })
    await ready()
    await userEvent.click(screen.getByRole('button', { name: 'Add user' }))
    const dialog = screen.getByRole('dialog', { name: 'Add user' })
    await userEvent.click(within(dialog).getByRole('button', { name: 'Add user' }))
    expect(within(dialog).getByText('Name is required')).toBeInTheDocument()
    expect(within(dialog).getByText('Enter a valid email address')).toBeInTheDocument()
    expect(api.callsTo('POST /api/users')).toHaveLength(0)

    await userEvent.type(within(dialog).getByLabelText('Name'), 'New Person')
    await userEvent.type(within(dialog).getByLabelText('Email'), 'new@netmonitor.local')
    await userEvent.type(within(dialog).getByLabelText('Password'), 'a-long-enough-password')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Add user' }))
    await waitFor(() => expect(api.lastCall('POST /api/users')?.body).toMatchObject({ name: 'New Person', email: 'new@netmonitor.local', role: 'ANALYST' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await waitFor(() => expect(api.callsTo('GET /api/users')).toHaveLength(2))
  })

  it('shows the server message when the email is already taken', async () => {
    renderUsers({ routes: { 'POST /api/users': reply(409, { detail: 'Email already in use' }) } })
    await ready()
    await userEvent.click(screen.getByRole('button', { name: 'Add user' }))
    const dialog = screen.getByRole('dialog', { name: 'Add user' })
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Dup')
    await userEvent.type(within(dialog).getByLabelText('Email'), 'admin@netmonitor.local')
    await userEvent.type(within(dialog).getByLabelText('Password'), 'a-long-enough-password')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Add user' }))
    expect(await within(dialog).findByText('Email already in use')).toBeInTheDocument()
  })

  it('edits a user without requiring a new password', async () => {
    const { api } = renderUsers({ routes: { 'PUT /api/users/2': { ...ANALYST, name: 'Renamed' } } })
    await ready()
    await userEvent.click(screen.getByRole('button', { name: 'Edit Network Analyst' }))
    const dialog = screen.getByRole('dialog', { name: 'Edit Network Analyst' })
    await userEvent.clear(within(dialog).getByLabelText('Name'))
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Renamed')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(api.lastCall('PUT /api/users/2')?.body).toEqual({ name: 'Renamed', email: 'analyst@netmonitor.local', role: 'ANALYST' }))
  })

  it('disables a user after confirmation, and enables a disabled one', async () => {
    const { api } = renderUsers({
      routes: { 'PATCH /api/users/2/status': { ...ANALYST, status: 'DISABLED' }, 'PATCH /api/users/3/status': { ...DISABLED, status: 'ACTIVE' } },
    })
    await ready()
    await userEvent.click(screen.getByRole('button', { name: 'Disable Network Analyst' }))
    await userEvent.click(within(screen.getByRole('dialog', { name: 'Disable Network Analyst?' })).getByRole('button', { name: 'Disable user' }))
    await waitFor(() => expect(api.lastCall('PATCH /api/users/2/status')?.body).toEqual({ status: 'DISABLED' }))

    await userEvent.click(await screen.findByRole('button', { name: 'Enable Old Analyst' }))
    await userEvent.click(within(screen.getByRole('dialog', { name: 'Enable Old Analyst?' })).getByRole('button', { name: 'Enable user' }))
    await waitFor(() => expect(api.lastCall('PATCH /api/users/3/status')?.body).toEqual({ status: 'ACTIVE' }))
  })

  it('shows the backend message when the last admin cannot be disabled', async () => {
    const other = { ...ADMIN, user_id: 5, name: 'Other Admin', email: 'other@netmonitor.local' }
    renderUsers({
      routes: { 'GET /api/users': paginated([ADMIN, other]), 'PATCH /api/users/5/status': reply(409, { detail: 'At least one active admin is required' }) },
    })
    await userEvent.click(await screen.findByRole('button', { name: 'Disable Other Admin' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Disable user' }))
    expect(await within(screen.getByRole('dialog')).findByText('At least one active admin is required')).toBeInTheDocument()
  })
})
