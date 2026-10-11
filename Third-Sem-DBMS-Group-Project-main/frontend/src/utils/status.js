
export const STATUS_TONES = {
  ACTIVE: { tone: 'ok', label: 'Active' },
  INACTIVE: { tone: 'muted', label: 'Inactive' },
  OFFLINE: { tone: 'muted', label: 'Offline' },
  UNKNOWN: { tone: 'warn', label: 'Unknown' },
  DISABLED: { tone: 'muted', label: 'Disabled' },
  ADMIN: { tone: 'accent', label: 'Admin' },
  ANALYST: { tone: 'neutral', label: 'Analyst' },
}

export const NODE_STATUSES = ['ACTIVE', 'INACTIVE', 'OFFLINE']
export const DEVICE_STATUSES = ['ACTIVE', 'INACTIVE', 'UNKNOWN']
export const USER_ROLES = ['ADMIN', 'ANALYST']
export const USER_STATUSES = ['ACTIVE', 'DISABLED']

export const DESTINATION_CATEGORIES = [
  'SEARCH',
  'SOCIAL',
  'DEVELOPMENT',
  'EDUCATION',
  'VIDEO',
  'CLOUD',
  'OTHER',
  'UNKNOWN',
]

export const titleCase = (value) => (value ? value.charAt(0) + value.slice(1).toLowerCase() : '')
