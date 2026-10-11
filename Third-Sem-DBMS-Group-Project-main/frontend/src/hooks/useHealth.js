import { useAsync } from './useAsync.js'
import { getApiHealth, getDatabaseHealth } from '../services/health.js'

export function useHealth(pollMs = 30000) {
  const api = useAsync((signal) => getApiHealth(signal), [], { pollMs })
  const database = useAsync((signal) => getDatabaseHealth(signal), [], { pollMs })

  const toCheck = (result, isHealthy) => {
    if (result.error) return { state: 'error', data: null, error: result.error }
    if (result.data === null) return { state: 'loading', data: null }
    return { state: isHealthy(result.data) ? 'ok' : 'error', data: result.data }
  }

  return {
    api: toCheck(api, (data) => data.status === 'ok'),
    database: toCheck(database, (data) => data.status === 'ok'),
    reload: () => {
      api.reload()
      database.reload()
    },
  }
}
