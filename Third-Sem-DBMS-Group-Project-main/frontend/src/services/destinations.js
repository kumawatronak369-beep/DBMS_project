import { request } from './api.js'

export const listDestinations = (params, signal) => request('/destinations', { params, signal })

export const getDestination = (id, signal) => request(`/destinations/${id}`, { signal })

export const getDestinationHistory = (id, params, signal) =>
  request(`/destinations/${id}/history`, { params, signal })
