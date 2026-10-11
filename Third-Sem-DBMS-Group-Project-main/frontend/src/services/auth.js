import { request } from './api.js'

export const login = (email, password) =>
  request('/auth/login', { method: 'POST', body: { email, password }, auth: false })

export const getCurrentUser = (signal) => request('/auth/me', { signal })

export const logout = () => request('/auth/logout', { method: 'POST' })
