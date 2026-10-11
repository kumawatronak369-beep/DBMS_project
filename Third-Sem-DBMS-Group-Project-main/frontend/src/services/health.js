import { request } from './api.js'

// /health is public; /health/db needs a signed-in user and answers 503 when the database is down
export const getApiHealth = (signal) => request('/health', { signal, auth: false })

export const getDatabaseHealth = (signal) => request('/health/db', { signal, okStatuses: [503] })
