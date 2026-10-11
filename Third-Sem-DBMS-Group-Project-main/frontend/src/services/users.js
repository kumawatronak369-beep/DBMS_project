import { request } from './api.js'

// All /users endpoints are ADMIN only (analysts receive 403).
export const listUsers = (params, signal) => request('/users', { params, signal })
export const createUser = (data) => request('/users', { method: 'POST', body: data })
export const updateUser = (id, data) => request(`/users/${id}`, { method: 'PUT', body: data })
export const setUserStatus = (id, status) =>
  request(`/users/${id}/status`, { method: 'PATCH', body: { status } })
