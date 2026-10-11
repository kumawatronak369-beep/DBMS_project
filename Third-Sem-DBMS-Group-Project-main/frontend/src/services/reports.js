import { request } from './api.js'

export const getTopDestinationsReport = (params, signal) =>
  request('/reports/top-destinations', { params, signal })

export const getTopDevicesReport = (params, signal) => request('/reports/top-devices', { params, signal })

export const getActivityByNode = (params, signal) => request('/reports/activity-by-node', { params, signal })

export const getActivityOverTime = (params, signal) =>
  request('/reports/activity-over-time', { params, signal })
