import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'

// Keeps filters and the page number in the URL so a view can be bookmarked or survive a refresh
export function useUrlState(defaults) {
  const [searchParams, setSearchParams] = useSearchParams()

  const values = useMemo(() => {
    const result = {}
    for (const key of Object.keys(defaults)) result[key] = searchParams.get(key) ?? defaults[key]
    return result
  }, [searchParams, defaults])

  const update = useCallback(
    (patch) => {
      setSearchParams(
        (previous) => {
          const next = new URLSearchParams(previous)
          for (const [key, value] of Object.entries(patch)) {
            if (value === '' || value === null || value === undefined || String(value) === defaults[key]) {
              next.delete(key)
            } else {
              next.set(key, String(value))
            }
          }
          if (!('page' in patch)) next.delete('page')
          return next
        },
        { replace: true },
      )
    },
    [setSearchParams, defaults],
  )

  return [values, update]
}
