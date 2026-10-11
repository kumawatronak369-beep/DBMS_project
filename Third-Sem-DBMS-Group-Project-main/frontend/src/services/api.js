// every HTTP call goes through here

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/$/, '')

let authToken = null
let unauthorizedHandler = null

export const setAuthToken = (token) => {
  authToken = token
}

export const setUnauthorizedHandler = (handler) => {
  unauthorizedHandler = handler
}

export class ApiError extends Error {
  constructor(message, status = 0, body = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status // 0 = the server could not be reached
    this.body = body
  }

  get isNetworkError() {
    return this.status === 0
  }
}

function messageFrom(status, body) {
  const detail = body?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const field = (item.loc ?? []).filter((part) => part !== 'body' && part !== 'query').join('.')
        const label = field.replace(/_/g, ' ').replace(/^ip\b/i, 'IP').replace(/^./, (c) => c.toUpperCase())
        const text = String(item.msg).replace(/^Value error, /, '')
        return field ? `${label}: ${text}` : text
      })
      .join('; ')
  }
  if (status === 401) return 'Your session has expired. Please sign in again.'
  if (status === 403) return 'You do not have permission to do that.'
  if (status === 404) return 'The requested item was not found.'
  if (status === 502 || status === 503 || status === 504) return 'The server is unavailable. Please try again shortly.'
  if (status >= 500) return 'The server ran into a problem. Please try again.'
  return `Request failed (${status}).`
}

function buildUrl(path, params) {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== null && value !== '') query.set(key, String(value))
  }
  const suffix = query.toString()
  return `${BASE_URL}${path}${suffix ? `?${suffix}` : ''}`
}

export async function request(path, { method = 'GET', params, body, signal, auth = true, okStatuses = [] } = {}) {
  const headers = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (auth && authToken) headers.Authorization = `Bearer ${authToken}`

  let response
  try {
    response = await fetch(buildUrl(path, params), {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError('Unable to reach the server. Check your connection and try again.', 0)
  }

  if (response.status === 204) return null
  const payload = await response.json().catch(() => null)
  if (response.ok || okStatuses.includes(response.status)) return payload

  if (response.status === 401 && auth && unauthorizedHandler) unauthorizedHandler()
  throw new ApiError(messageFrom(response.status, payload), response.status, payload)
}
