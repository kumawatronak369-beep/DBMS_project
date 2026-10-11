import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterEach, beforeEach, expect, vi } from 'vitest'
import { setAuthToken, setUnauthorizedHandler } from '../services/api.js'
import { takeUnmockedRequests } from './fetchMock.js'

configure({ asyncUtilTimeout: 5000 })

// jsdom has no ResizeObserver and cannot lay charts out
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
}

vi.mock('../components/charts/ActivityChart.jsx', () => ({
  ActivityChart: ({ points, bucket }) => (
    <div
      data-testid="activity-chart"
      data-bucket={bucket}
      data-points={points.length}
      data-total={points.reduce((sum, point) => sum + point.event_count, 0)}
    />
  ),
}))
vi.mock('../components/charts/BarCharts.jsx', () => ({
  TopDestinationsChart: ({ rows }) => (
    <div data-testid="top-destinations-chart" data-labels={rows.map((row) => row.domain ?? row.ip_address).join(',')} />
  ),
  NodeActivityChart: ({ rows }) => (
    <div data-testid="node-activity-chart" data-labels={rows.map((row) => row.node_code).join(',')} />
  ),
}))

let consoleProblems = []

beforeEach(() => {
  consoleProblems = []
  vi.spyOn(console, 'error').mockImplementation((...args) => consoleProblems.push(['console.error', ...args]))
  vi.spyOn(console, 'warn').mockImplementation((...args) => consoleProblems.push(['console.warn', ...args]))
})

afterEach(() => {
  cleanup()
  setAuthToken(null)
  setUnauthorizedHandler(null)
  localStorage.clear()
  document.title = ''
  vi.useRealTimers()

  const unmocked = takeUnmockedRequests()
  const problems = consoleProblems
  vi.restoreAllMocks()
  expect(unmocked, 'requests the test did not mock').toEqual([])
  expect(problems, 'unexpected console.error / console.warn').toEqual([])
})
