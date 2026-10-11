import { request } from './api.js'

export const getSummary = (signal) => request('/dashboard/summary', { signal })

export const getActivity = (params, signal) => request('/dashboard/activity', { params, signal })

export const getTopDestinations = (params, signal) =>
  request('/dashboard/top-destinations', { params, signal })

export const getTopDevices = (params, signal) => request('/dashboard/top-devices', { params, signal })
