import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { installFetch, reply } from '../../test/fetchMock.js'
import { ADMIN, ANALYST, node } from '../../test/fixtures.js'
import { ConfirmModal } from './ConfirmModal.jsx'
import { NodeFormModal } from './NodeFormModal.jsx'
import { UserFormModal } from './UserFormModal.jsx'

function deferred() {
  let resolve
  let reject
  const promise = new Promise((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('ConfirmModal', () => {
  const setup = (onConfirm) => {
    const onClose = vi.fn()
    render(<ConfirmModal title="Disable Lab A?" message="Its history is preserved." confirmLabel="Disable node" danger onConfirm={onConfirm} onClose={onClose} />)
    return { onClose }
  }

  it('asks, then runs the action and closes', async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined)
    const { onClose } = setup(onConfirm)
    expect(screen.getByRole('dialog', { name: 'Disable Lab A?' })).toBeInTheDocument()
    expect(screen.getByText('Its history is preserved.')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Disable node' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1))
  })

  it('cancels without running the action', async () => {
    const onConfirm = vi.fn()
    const { onClose } = setup(onConfirm)
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onConfirm).not.toHaveBeenCalled()
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('stays open and shows the reason when the action fails', async () => {
    const { onClose } = setup(vi.fn().mockRejectedValue(new Error('At least one active administrator must remain')))
    await userEvent.click(screen.getByRole('button', { name: 'Disable node' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('At least one active administrator must remain')
    expect(onClose).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Disable node' })).toBeEnabled()
  })

  it('cannot be double-submitted while the action is running', async () => {
    const gate = deferred()
    const onConfirm = vi.fn(() => gate.promise)
    const { onClose } = setup(onConfirm)
    await userEvent.click(screen.getByRole('button', { name: 'Disable node' }))
    expect(screen.getByRole('button', { name: 'Disable node' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Disable node' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)

    gate.resolve()
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })
})

describe('NodeFormModal', () => {
  const fill = async (user, values) => {
    for (const [label, value] of Object.entries(values)) {
      const field = screen.getByLabelText(label)
      await user.clear(field)
      await user.type(field, value)
    }
  }

  it('validates required fields before sending anything', async () => {
    const api = installFetch()
    render(<NodeFormModal onClose={() => {}} onSaved={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: 'Add node' }))
    for (const message of ['Node code is required', 'Name is required', 'IP address is required', 'Location is required']) {
      expect(screen.getByText(message)).toBeInTheDocument()
    }
    expect(api.calls).toHaveLength(0)
  })

  it('creates a node with the entered values (a blank description becomes null)', async () => {
    const created = node({ node_id: 9, node_code: 'LAB-Z', node_name: 'Lab Z' })
    const api = installFetch({ 'POST /api/nodes': reply(201, created) })
    const onSaved = vi.fn()
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<NodeFormModal onClose={onClose} onSaved={onSaved} />)

    await fill(user, { 'Node code': 'LAB-Z', Name: 'Lab Z', 'IP address': '10.0.0.9', Location: 'Block Z' })
    await user.type(screen.getByLabelText('Description'), '   ')
    await user.click(screen.getByRole('button', { name: 'Add node' }))

    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(created))
    expect(onClose).toHaveBeenCalled()
    expect(api.lastCall('POST /api/nodes').body).toEqual({
      node_code: 'LAB-Z',
      node_name: 'Lab Z',
      ip_address: '10.0.0.9',
      location: 'Block Z',
      description: null,
    })
  })

  it('shows the server error (e.g. a duplicate code) and stays open for a correction', async () => {
    installFetch({ 'POST /api/nodes': reply(409, { detail: "Node code 'LAB-A' is already in use" }) })
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<NodeFormModal onClose={onClose} onSaved={() => {}} />)
    await fill(user, { 'Node code': 'LAB-A', Name: 'Dup', 'IP address': '10.0.0.9', Location: 'Z' })
    await user.click(screen.getByRole('button', { name: 'Add node' }))

    expect(await screen.findByRole('alert')).toHaveTextContent("Node code 'LAB-A' is already in use")
    expect(onClose).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Add node' })).toBeEnabled()
  })

  it('shows a readable message for a validation error from the server', async () => {
    installFetch({
      'POST /api/nodes': reply(422, { detail: [{ loc: ['body', 'ip_address'], msg: 'Value error, must be a valid IPv4 or IPv6 address' }] }),
    })
    const user = userEvent.setup()
    render(<NodeFormModal onClose={() => {}} onSaved={() => {}} />)
    await fill(user, { 'Node code': 'X', Name: 'X', 'IP address': 'nope', Location: 'X' })
    await user.click(screen.getByRole('button', { name: 'Add node' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('IP address: must be a valid IPv4 or IPv6 address')
  })

  it('rejects an over-long description locally', async () => {
    const api = installFetch()
    const user = userEvent.setup()
    render(<NodeFormModal onClose={() => {}} onSaved={() => {}} />)
    await fill(user, { 'Node code': 'X', Name: 'X', 'IP address': '10.0.0.1', Location: 'X' })
    fireEvent.change(screen.getByLabelText('Description'), { target: { value: 'x'.repeat(501) } })
    await user.click(screen.getByRole('button', { name: 'Add node' }))
    expect(screen.getByText('At most 500 characters')).toBeInTheDocument()
    expect(api.calls).toHaveLength(0)
  })

  it('edits an existing node: prefilled, saved with PUT', async () => {
    const existing = node({ description: 'Ground floor lab' })
    const api = installFetch({ 'PUT /api/nodes/1': { ...existing, node_name: 'Renamed Lab' } })
    const onSaved = vi.fn()
    const user = userEvent.setup()
    render(<NodeFormModal node={existing} onClose={() => {}} onSaved={onSaved} />)

    expect(screen.getByRole('dialog', { name: 'Edit Computer Lab A' })).toBeInTheDocument()
    expect(screen.getByLabelText('Node code')).toHaveValue('LAB-A')
    expect(screen.getByLabelText('Description')).toHaveValue('Ground floor lab')

    await fill(user, { Name: 'Renamed Lab' })
    await user.click(screen.getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    expect(api.lastCall('PUT /api/nodes/1').body).toMatchObject({ node_name: 'Renamed Lab', node_code: 'LAB-A', description: 'Ground floor lab' })
  })
})

describe('UserFormModal', () => {
  it('validates name, email and password locally', async () => {
    const api = installFetch()
    const user = userEvent.setup()
    render(<UserFormModal onClose={() => {}} onSaved={() => {}} />)
    await user.type(screen.getByLabelText('Email'), 'not-an-email')
    await user.type(screen.getByLabelText('Password'), 'short')
    await user.click(screen.getByRole('button', { name: 'Add user' }))

    expect(screen.getByText('Name is required')).toBeInTheDocument()
    expect(screen.getByText('Enter a valid email address')).toBeInTheDocument()
    expect(screen.getByText('At least 8 characters')).toBeInTheDocument()
    expect(api.calls).toHaveLength(0)
  })

  it('creates a user with the chosen role (analyst by default)', async () => {
    const created = { ...ANALYST, user_id: 5, name: 'Dana', email: 'dana@netmonitor.local' }
    const api = installFetch({ 'POST /api/users': reply(201, created) })
    const onSaved = vi.fn()
    const user = userEvent.setup()
    render(<UserFormModal onClose={() => {}} onSaved={onSaved} />)

    expect(screen.getByLabelText('Role')).toHaveValue('ANALYST')
    await user.type(screen.getByLabelText('Name'), '  Dana  ')
    await user.type(screen.getByLabelText('Email'), 'dana@netmonitor.local')
    await user.type(screen.getByLabelText('Password'), 'long-enough-password')
    await user.selectOptions(screen.getByLabelText('Role'), 'ADMIN')
    await user.click(screen.getByRole('button', { name: 'Add user' }))

    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(created))
    expect(api.lastCall('POST /api/users').body).toEqual({
      name: 'Dana',
      email: 'dana@netmonitor.local',
      role: 'ADMIN',
      password: 'long-enough-password',
    })
  })

  it('shows the server error for a duplicate email', async () => {
    installFetch({ 'POST /api/users': reply(409, { detail: "Email 'dana@netmonitor.local' is already in use" }) })
    const user = userEvent.setup()
    render(<UserFormModal onClose={() => {}} onSaved={() => {}} />)
    await user.type(screen.getByLabelText('Name'), 'Dana')
    await user.type(screen.getByLabelText('Email'), 'dana@netmonitor.local')
    await user.type(screen.getByLabelText('Password'), 'long-enough-password')
    await user.click(screen.getByRole('button', { name: 'Add user' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('is already in use')
  })

  it('edits without touching the password unless a new one is typed', async () => {
    const api = installFetch({ 'PUT /api/users/2': ANALYST })
    const user = userEvent.setup()
    render(<UserFormModal user={ANALYST} onClose={() => {}} onSaved={() => {}} />)

    expect(screen.getByRole('dialog', { name: 'Edit Network Analyst' })).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toHaveValue('analyst@netmonitor.local')
    expect(screen.getByLabelText('New password')).toHaveValue('')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    await waitFor(() => expect(api.callsTo('PUT /api/users/2')).toHaveLength(1))
    expect(api.lastCall('PUT /api/users/2').body).toEqual({ name: 'Network Analyst', email: 'analyst@netmonitor.local', role: 'ANALYST' })
    expect(api.lastCall('PUT /api/users/2').body).not.toHaveProperty('password')
  })

  it('sends a new password when one is entered, and enforces the minimum length', async () => {
    const api = installFetch({ 'PUT /api/users/1': ADMIN })
    const user = userEvent.setup()
    render(<UserFormModal user={ADMIN} onClose={() => {}} onSaved={() => {}} />)

    await user.type(screen.getByLabelText('New password'), 'short')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))
    expect(screen.getByText('At least 8 characters')).toBeInTheDocument()
    expect(api.calls).toHaveLength(0)

    await user.clear(screen.getByLabelText('New password'))
    await user.type(screen.getByLabelText('New password'), 'a-new-good-password')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(api.callsTo('PUT /api/users/1')).toHaveLength(1))
    expect(api.lastCall('PUT /api/users/1').body.password).toBe('a-new-good-password')
  })
})
