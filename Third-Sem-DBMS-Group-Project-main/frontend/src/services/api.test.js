import { describe, expect, it, vi } from 'vitest'
import { installFetch, networkFailure, reply } from '../test/fetchMock.js'
import { ApiError, request, setAuthToken, setUnauthorizedHandler } from './api.js'

describe('request: building the call', () => {
  it('sends GET with JSON accept header and drops empty parameters', async () => {
    const api = installFetch({ 'GET /api/nodes': { items: [] } })
    await request('/nodes', { params: { search: 'lab', status: '', page: 2, pageSize: undefined, x: null } })
    const call = api.lastCall('GET /api/nodes')
    expect(call.query).toEqual({ search: 'lab', page: '2' })
    expect(call.headers.accept).toBe('application/json')
    expect(call.headers['content-type']).toBeUndefined()
  })

  it('sends a JSON body with the right content type', async () => {
    const api = installFetch({ 'POST /api/nodes': reply(201, { node_id: 9 }) })
    const result = await request('/nodes', { method: 'POST', body: { node_code: 'X' } })
    expect(result).toEqual({ node_id: 9 })
    const call = api.lastCall('POST /api/nodes')
    expect(call.body).toEqual({ node_code: 'X' })
    expect(call.headers['content-type']).toBe('application/json')
  })

  it('sends the bearer token when one is set, and not when auth is off', async () => {
    const api = installFetch({ 'GET /api/nodes': {}, 'POST /api/auth/login': {} })
    setAuthToken('secret-token')
    await request('/nodes')
    await request('/auth/login', { method: 'POST', body: {}, auth: false })
    expect(api.lastCall('GET /api/nodes').headers.authorization).toBe('Bearer secret-token')
    expect(api.lastCall('POST /api/auth/login').headers.authorization).toBeUndefined()
  })

  it('sends no Authorization header when signed out', async () => {
    const api = installFetch({ 'GET /api/nodes': {} })
    await request('/nodes')
    expect(api.lastCall('GET /api/nodes').headers.authorization).toBeUndefined()
  })

  it('returns null for 204 No Content', async () => {
    installFetch({ 'POST /api/auth/logout': reply(204) })
    expect(await request('/auth/logout', { method: 'POST' })).toBeNull()
  })
})

describe('request: errors', () => {
  it('turns a string detail into the ApiError message', async () => {
    installFetch({ 'GET /api/nodes/9': reply(404, { detail: 'Node 9 not found' }) })
    const error = await request('/nodes/9').catch((e) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 404, message: 'Node 9 not found', isNetworkError: false })
  })

  it('turns validation details into readable text without technical noise', async () => {
    installFetch({
      'POST /api/nodes': reply(422, {
        detail: [
          { loc: ['body', 'ip_address'], msg: 'Value error, must be a valid IPv4 or IPv6 address' },
          { loc: ['body', 'node_code'], msg: 'String should have at least 1 character' },
        ],
      }),
    })
    const error = await request('/nodes', { method: 'POST', body: {} }).catch((e) => e)
    expect(error.message).toBe(
      'IP address: must be a valid IPv4 or IPv6 address; Node code: String should have at least 1 character',
    )
  })

  it.each([
    [403, 'You do not have permission to do that.'],
    [404, 'The requested item was not found.'],
    [502, 'The server is unavailable. Please try again shortly.'],
    [503, 'The server is unavailable. Please try again shortly.'],
    [500, 'The server ran into a problem. Please try again.'],
    [418, 'Request failed (418).'],
  ])('uses a friendly default message for HTTP %i without a usable body', async (status, message) => {
    installFetch({ 'GET /api/x': reply(status, '<html>proxy error</html>') })
    await expect(request('/x')).rejects.toMatchObject({ status, message })
  })

  it('reports an unreachable server as a network error (status 0)', async () => {
    installFetch({ 'GET /api/nodes': () => networkFailure() })
    const error = await request('/nodes').catch((e) => e)
    expect(error).toMatchObject({ status: 0, isNetworkError: true })
    expect(error.message).toMatch(/Unable to reach the server/)
  })

  it('lets an aborted request through untouched so callers can ignore it', async () => {
    installFetch({ 'GET /api/nodes': {} })
    const controller = new AbortController()
    controller.abort()
    await expect(request('/nodes', { signal: controller.signal })).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('can return the body of an expected non-2xx answer (health check 503)', async () => {
    installFetch({ 'GET /api/health/db': reply(503, { status: 'error', database: 'unreachable' }) })
    const body = await request('/health/db', { auth: false, okStatuses: [503] })
    expect(body).toEqual({ status: 'error', database: 'unreachable' })
  })
})

describe('request: expired sessions', () => {
  it('calls the unauthorized handler when an authenticated request gets 401', async () => {
    installFetch({ 'GET /api/nodes': reply(401, { detail: 'Invalid or expired token' }) })
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    await expect(request('/nodes')).rejects.toMatchObject({ status: 401 })
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('does not treat a failed login (401 with auth off) as an expired session', async () => {
    installFetch({ 'POST /api/auth/login': reply(401, { detail: 'Invalid email or password' }) })
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    await expect(request('/auth/login', { method: 'POST', body: {}, auth: false })).rejects.toMatchObject({
      message: 'Invalid email or password',
    })
    expect(handler).not.toHaveBeenCalled()
  })

  it('does not call the handler for other errors', async () => {
    installFetch({ 'GET /api/nodes': reply(403, { detail: 'nope' }) })
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    await expect(request('/nodes')).rejects.toMatchObject({ status: 403 })
    expect(handler).not.toHaveBeenCalled()
  })
})
