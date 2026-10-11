import { request } from './api.js'

export const listNodes = (params, signal) => request('/nodes', { params, signal })

export const getNode = (id, signal) => request(`/nodes/${id}`, { signal })

// ADMIN only
export const createNode = (data) => request('/nodes', { method: 'POST', body: data })
export const updateNode = (id, data) => request(`/nodes/${id}`, { method: 'PUT', body: data })
export const setNodeStatus = (id, status) =>
  request(`/nodes/${id}/status`, { method: 'PATCH', body: { status } })
