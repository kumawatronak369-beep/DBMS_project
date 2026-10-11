import { request } from './api.js'

export const listHistory = (params, signal) => request('/history', { params, signal })

export const getHistoryEvent = (id, signal) => request(`/history/${id}`, { signal })
