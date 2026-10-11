import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AuthProvider } from '../hooks/AuthProvider.jsx'
import AppRoutes from '../routes/AppRoutes.jsx'
import { installFetch } from './fetchMock.js'
import {
  ADMIN,
  activity,
  destination,
  device,
  historyEvent,
  node,
  nodeActivity,
  paginated,
  summary,
  topDestination,
  topDevice,
} from './fixtures.js'

export const SESSION_KEY = 'nm.session'

export function seedSession(user = ADMIN, { token = 'test-token', expiresInMs = 60 * 60 * 1000 } = {}) {
  localStorage.setItem(SESSION_KEY, JSON.stringify({ token, user, expiresAt: Date.now() + expiresInMs }))
}

export function healthRoutes() {
  return {
    'GET /api/health': { status: 'ok', app: 'Private Network Monitoring System' },
    'GET /api/health/db': {
      status: 'ok',
      database: 'connected',
      tables: ['collector_api_keys', 'destinations', 'devices', 'network_history', 'nodes', 'users'],
      missing_tables: [],
    },
  }
}

export function baseRoutes(user = ADMIN) {
  return { 'GET /api/auth/me': user, ...healthRoutes() }
}

export function dashboardRoutes(overrides = {}) {
  return {
    'GET /api/dashboard/summary': summary(),
    'GET /api/dashboard/activity': activity(),
    'GET /api/dashboard/top-destinations': [topDestination(), topDestination({ destination_id: 2, domain: 'github.com', ip_address: '203.0.113.20', event_count: 96 })],
    'GET /api/dashboard/top-devices': [topDevice(), topDevice({ device_id: 2, device_identifier: 'PC-LAB-B-002', node_name: 'Computer Lab B', event_count: 57 })],
    'GET /api/reports/activity-by-node': [nodeActivity(), nodeActivity({ node_id: 2, node_code: 'LAB-B', node_name: 'Computer Lab B', event_count: 225 })],
    'GET /api/history': paginated([historyEvent(), historyEvent({ history_id: 102, device_identifier: 'PC-LIB-002', node_code: 'LIB-01', domain: null, destination_ip: '192.0.2.77' })], { total: 2 }),
    'GET /api/nodes': paginated([node(), node({ node_id: 2, node_code: 'LAB-B', node_name: 'Computer Lab B', status: 'OFFLINE', last_seen: null })]),
    'GET /api/devices': paginated([device(), device({ device_id: 2, device_identifier: 'PC-LAB-B-002', status: 'UNKNOWN', node_name: 'Computer Lab B' })]),
    ...overrides,
  }
}

export function allPageRoutes(overrides = {}) {
  return {
    ...dashboardRoutes(),
    'GET /api/destinations': paginated([destination(), destination({ destination_id: 12, domain: null, ip_address: '192.0.2.77', category: 'UNKNOWN' })]),
    'GET /api/reports/top-destinations': [topDestination()],
    'GET /api/reports/top-devices': [topDevice()],
    'GET /api/reports/activity-over-time': activity(),
    'GET /api/users': paginated([ADMIN]),
    ...overrides,
  }
}

export function renderWithProviders(ui, { route = '/', user = null } = {}) {
  if (user) seedSession(user)
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AuthProvider>{ui}</AuthProvider>
    </MemoryRouter>,
  )
}

export function renderApp(route = '/', { user = ADMIN, routes = {} } = {}) {
  const api = installFetch({ ...(user ? baseRoutes(user) : healthRoutes()), ...routes })
  const view = renderWithProviders(<AppRoutes />, { route, user })
  return { api, ...view }
}
