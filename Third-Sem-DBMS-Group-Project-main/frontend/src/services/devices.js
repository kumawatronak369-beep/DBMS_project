import { request } from './api.js'

export const listDevices = (params, signal) => request('/devices', { params, signal })

export const getDevice = (id, signal) => request(`/devices/${id}`, { signal })

export const getDeviceHistory = (id, params, signal) =>
  request(`/devices/${id}/history`, { params, signal })
