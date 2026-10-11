import { vi } from 'vitest'

// Fake backend for tests: declare the requests you expect and what to answer

let active = null

export const reply = (status, body = null) => ({ __reply: true, status, body })

function toResponse(value) {
  const { status, body } = value?.__reply ? value : { status: 200, body: value }
  if (status === 204 || body === null) return new Response(null, { status })
  return new Response(typeof body === 'string' ? body : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': typeof body === 'string' ? 'text/plain' : 'application/json' },
  })
}

function rejectOnAbort(signal) {
  return new Promise((_, reject) => {
    if (!signal) return
    const abort = () => reject(new DOMException('The operation was aborted.', 'AbortError'))
    if (signal.aborted) abort()
    else signal.addEventListener('abort', abort, { once: true })
  })
}

export function installFetch(routes = {}) {
  const table = { ...routes }
  const calls = []
  const unmocked = []

  const fetchMock = vi.fn(async (input, init = {}) => {
    const url = new URL(String(input), 'http://localhost')
    const method = (init.method ?? 'GET').toUpperCase()
    const key = `${method} ${url.pathname}`
    const call = {
      key,
      method,
      path: url.pathname,
      query: Object.fromEntries(url.searchParams),
      body: init.body ? JSON.parse(init.body) : undefined,
      headers: Object.fromEntries(new Headers(init.headers).entries()),
    }
    calls.push(call)
    if (init.signal?.aborted) throw new DOMException('The operation was aborted.', 'AbortError')

    if (!(key in table)) {
      unmocked.push(key)
      return toResponse(reply(599, { detail: `Unmocked request: ${key}` }))
    }
    const entry = table[key]
    const pending = typeof entry === 'function' ? entry(call) : entry
    const value = await Promise.race([Promise.resolve(pending), rejectOnAbort(init.signal)])
    if (value instanceof Error) throw value
    return toResponse(value)
  })

  vi.stubGlobal('fetch', fetchMock)

  const api = {
    fetch: fetchMock,
    calls,
    unmocked,
    set(key, value) {
      table[key] = value
    },
    callsTo: (key) => calls.filter((call) => call.key === key),
    lastCall: (key) => calls.filter((call) => call.key === key).at(-1),
  }
  active = api
  return api
}

export function takeUnmockedRequests() {
  const found = active ? [...active.unmocked] : []
  active = null
  return found
}

export const networkFailure = () => new TypeError('Failed to fetch')
