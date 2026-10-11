
export const ADMIN = {
  user_id: 1,
  name: 'System Administrator',
  email: 'admin@netmonitor.local',
  role: 'ADMIN',
  status: 'ACTIVE',
  created_at: '2026-09-19T22:00:59',
  last_login: '2026-09-20T08:00:00',
}

export const ANALYST = {
  user_id: 2,
  name: 'Network Analyst',
  email: 'analyst@netmonitor.local',
  role: 'ANALYST',
  status: 'ACTIVE',
  created_at: '2026-09-19T22:00:59',
  last_login: null,
}

export const paginated = (items, { page = 1, pageSize = 25, total = items.length } = {}) => ({
  items,
  total,
  page,
  page_size: pageSize,
})

export const node = (overrides = {}) => ({
  node_id: 1,
  node_code: 'LAB-A',
  node_name: 'Computer Lab A',
  ip_address: '10.10.1.1',
  location: 'Science Block',
  description: null,
  status: 'ACTIVE',
  registered_at: '2026-09-19T22:00:59',
  last_seen: '2026-09-19T20:29:00',
  device_count: 5,
  ...overrides,
})

export const nodeDetail = (overrides = {}) => ({
  ...node(),
  event_count: 260,
  recent_activity: [historyEvent()],
  activity_by_day: [
    { bucket: '2026-09-19T00:00:00', event_count: 40 },
    { bucket: '2026-09-20T00:00:00', event_count: 10 },
  ],
  ...overrides,
})

export const device = (overrides = {}) => ({
  device_id: 1,
  node_id: 1,
  node_code: 'LAB-A',
  node_name: 'Computer Lab A',
  device_identifier: 'PC-LAB-A-001',
  device_name: 'LAB-A Workstation 1',
  ip_address: '192.168.10.21',
  mac_address: '02:00:01:00:00:01',
  hostname: 'pc-lab-a-001.campus.local',
  status: 'ACTIVE',
  first_seen: '2026-09-13T01:12:11',
  last_seen: '2026-09-19T20:29:00',
  ...overrides,
})

export const deviceDetail = (overrides = {}) => ({
  ...device(),
  total_events: 57,
  activity_by_day: [{ bucket: '2026-09-19T00:00:00', event_count: 9 }],
  recent_destinations: [
    {
      destination_id: 2,
      domain: 'github.com',
      ip_address: '203.0.113.20',
      category: 'DEVELOPMENT',
      visits: 10,
      last_visit: '2026-09-19T05:45:20',
    },
  ],
  ...overrides,
})

export const destination = (overrides = {}) => ({
  destination_id: 2,
  ip_address: '203.0.113.20',
  domain: 'github.com',
  category: 'DEVELOPMENT',
  first_seen: '2026-09-13T05:04:45',
  last_seen: '2026-09-19T15:20:31',
  event_count: 98,
  unique_devices: 17,
  ...overrides,
})

export const destinationDetail = (overrides = {}) => ({
  ...destination(),
  nodes: [{ node_id: 1, node_code: 'LAB-A', node_name: 'Computer Lab A', event_count: 37 }],
  devices: [
    {
      device_id: 1,
      device_identifier: 'PC-LAB-A-001',
      ip_address: '192.168.10.21',
      node_name: 'Computer Lab A',
      access_count: 10,
      last_access: '2026-09-19T05:45:20',
    },
  ],
  ...overrides,
})

export const historyEvent = (overrides = {}) => ({
  history_id: 101,
  observed_at: '2026-09-19T20:15:32',
  device_id: 1,
  device_identifier: 'PC-LAB-A-001',
  device_name: 'LAB-A Workstation 1',
  device_ip: '192.168.10.21',
  node_id: 1,
  node_code: 'LAB-A',
  node_name: 'Computer Lab A',
  destination_id: 2,
  destination_ip: '203.0.113.20',
  domain: 'github.com',
  category: 'DEVELOPMENT',
  protocol: null,
  source_port: null,
  destination_port: null,
  ...overrides,
})

export const user = (overrides = {}) => ({ ...ANALYST, ...overrides })

export const summary = (overrides = {}) => ({
  active_nodes: 4,
  registered_devices: 17,
  todays_events: 22,
  known_destinations: 12,
  ...overrides,
})

export const activity = (overrides = {}) => ({
  start: '2026-09-19T09:00:00',
  end: '2026-09-20T09:00:00',
  bucket: 'hour',
  points: [
    { bucket: '2026-09-20T07:00:00', event_count: 3 },
    { bucket: '2026-09-20T08:00:00', event_count: 9 },
  ],
  ...overrides,
})

export const topDestination = (overrides = {}) => ({
  destination_id: 6,
  domain: 'google.com',
  ip_address: '198.51.100.10',
  category: 'SEARCH',
  event_count: 144,
  unique_devices: 17,
  ...overrides,
})

export const topDevice = (overrides = {}) => ({
  device_id: 1,
  device_identifier: 'PC-LAB-A-001',
  ip_address: '192.168.10.21',
  node_id: 1,
  node_name: 'Computer Lab A',
  event_count: 54,
  ...overrides,
})

export const nodeActivity = (overrides = {}) => ({
  node_id: 1,
  node_code: 'LAB-A',
  node_name: 'Computer Lab A',
  event_count: 249,
  unique_devices: 5,
  ...overrides,
})
