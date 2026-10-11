import { describe, expect, it } from 'vitest'
import { installFetch, reply } from '../test/fetchMock.js'
import { setAuthToken } from './api.js'
import * as auth from './auth.js'
import * as dashboard from './dashboard.js'
import * as destinations from './destinations.js'
import * as devices from './devices.js'
import * as health from './health.js'
import * as history from './history.js'
import * as nodes from './nodes.js'
import * as reports from './reports.js'
import * as users from './users.js'

const NODE_BODY = { node_code: 'LAB-Z', node_name: 'Lab Z', ip_address: '10.0.0.9', location: 'Z', description: null }

const CASES = [
  ['nodes.listNodes', () => nodes.listNodes({ search: 'lab', status: 'ACTIVE', page: 2, pageSize: 25 }), 'GET /api/nodes', { search: 'lab', status: 'ACTIVE', page: '2', pageSize: '25' }],
  ['nodes.getNode', () => nodes.getNode(7), 'GET /api/nodes/7'],
  ['nodes.createNode', () => nodes.createNode(NODE_BODY), 'POST /api/nodes', {}, NODE_BODY],
  ['nodes.updateNode', () => nodes.updateNode(7, NODE_BODY), 'PUT /api/nodes/7', {}, NODE_BODY],
  ['nodes.setNodeStatus', () => nodes.setNodeStatus(7, 'INACTIVE'), 'PATCH /api/nodes/7/status', {}, { status: 'INACTIVE' }],
  ['devices.listDevices', () => devices.listDevices({ nodeId: 3, status: 'ACTIVE' }), 'GET /api/devices', { nodeId: '3', status: 'ACTIVE' }],
  ['devices.getDevice', () => devices.getDevice(4), 'GET /api/devices/4'],
  ['devices.getDeviceHistory', () => devices.getDeviceHistory(4, { range: '7d', page: 2 }), 'GET /api/devices/4/history', { range: '7d', page: '2' }],
  ['destinations.listDestinations', () => destinations.listDestinations({ category: 'VIDEO', search: 'you' }), 'GET /api/destinations', { category: 'VIDEO', search: 'you' }],
  ['destinations.getDestination', () => destinations.getDestination(5), 'GET /api/destinations/5'],
  ['destinations.getDestinationHistory', () => destinations.getDestinationHistory(5, { startDate: '2026-09-01', endDate: '2026-09-02' }), 'GET /api/destinations/5/history', { startDate: '2026-09-01', endDate: '2026-09-02' }],
  ['history.listHistory', () => history.listHistory({ q: 'github', nodeId: 1, destinationId: 2, startDate: '2026-09-01' }), 'GET /api/history', { q: 'github', nodeId: '1', destinationId: '2', startDate: '2026-09-01' }],
  ['history.getHistoryEvent', () => history.getHistoryEvent(101), 'GET /api/history/101'],
  ['dashboard.getSummary', () => dashboard.getSummary(), 'GET /api/dashboard/summary'],
  ['dashboard.getActivity', () => dashboard.getActivity({ range: '24h' }), 'GET /api/dashboard/activity', { range: '24h' }],
  ['dashboard.getTopDestinations', () => dashboard.getTopDestinations({ range: '7d', limit: 6 }), 'GET /api/dashboard/top-destinations', { range: '7d', limit: '6' }],
  ['dashboard.getTopDevices', () => dashboard.getTopDevices({ limit: 6 }), 'GET /api/dashboard/top-devices', { limit: '6' }],
  ['reports.getTopDestinationsReport', () => reports.getTopDestinationsReport({ range: '30d', limit: 10 }), 'GET /api/reports/top-destinations', { range: '30d', limit: '10' }],
  ['reports.getTopDevicesReport', () => reports.getTopDevicesReport({ range: '30d' }), 'GET /api/reports/top-devices', { range: '30d' }],
  ['reports.getActivityByNode', () => reports.getActivityByNode({ range: '24h' }), 'GET /api/reports/activity-by-node', { range: '24h' }],
  ['reports.getActivityOverTime', () => reports.getActivityOverTime({ range: '7d', nodeId: 2 }), 'GET /api/reports/activity-over-time', { range: '7d', nodeId: '2' }],
  ['users.listUsers', () => users.listUsers({ role: 'ADMIN' }), 'GET /api/users', { role: 'ADMIN' }],
  ['users.createUser', () => users.createUser({ name: 'A', email: 'a@b.c', password: 'password1', role: 'ANALYST' }), 'POST /api/users', {}, { name: 'A', email: 'a@b.c', password: 'password1', role: 'ANALYST' }],
  ['users.updateUser', () => users.updateUser(3, { name: 'B', email: 'b@c.d', role: 'ADMIN' }), 'PUT /api/users/3', {}, { name: 'B', email: 'b@c.d', role: 'ADMIN' }],
  ['users.setUserStatus', () => users.setUserStatus(3, 'DISABLED'), 'PATCH /api/users/3/status', {}, { status: 'DISABLED' }],
  ['auth.getCurrentUser', () => auth.getCurrentUser(), 'GET /api/auth/me'],
  ['auth.logout', () => auth.logout(), 'POST /api/auth/logout'],
]

describe('service functions', () => {
  it.each(CASES)('%s calls the right endpoint', async (_label, call, key, query = {}, body) => {
    const api = installFetch({ [key]: reply(200, {}) })
    setAuthToken('tok')
    await call()
    expect(api.callsTo(key)).toHaveLength(1)
    const sent = api.lastCall(key)
    expect(sent.query).toEqual(query)
    expect(sent.body).toEqual(body)
    expect(sent.headers.authorization).toBe('Bearer tok')
  })

  it('login sends credentials without any token', async () => {
    const api = installFetch({ 'POST /api/auth/login': { access_token: 't', expires_in: 3600, user: {} } })
    setAuthToken('stale-token')
    await auth.login('a@b.c', 'pw')
    const call = api.lastCall('POST /api/auth/login')
    expect(call.body).toEqual({ email: 'a@b.c', password: 'pw' })
    expect(call.headers.authorization).toBeUndefined()
  })

  it('only the liveness check is public; the database check sends the token and accepts a 503 body', async () => {
    const api = installFetch({
      'GET /api/health': { status: 'ok' },
      'GET /api/health/db': reply(503, { status: 'error', database: 'unreachable', tables: [], missing_tables: [] }),
    })
    setAuthToken('tok')
    expect(await health.getApiHealth()).toEqual({ status: 'ok' })
    expect((await health.getDatabaseHealth()).database).toBe('unreachable')
    expect(api.lastCall('GET /api/health').headers.authorization).toBeUndefined()
    expect(api.lastCall('GET /api/health/db').headers.authorization).toBe('Bearer tok')
  })
})
