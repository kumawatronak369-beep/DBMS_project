import { useCallback, useEffect, useRef, useState } from 'react'

// Runs load(signal) whenever deps change and tracks { data, error, loading }
export function useAsync(load, deps = [], { pollMs = 0, enabled = true } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: enabled })
  const [tick, setTick] = useState(0)
  const loadRef = useRef(load)

  useEffect(() => {
    loadRef.current = load
  })

  useEffect(() => {
    if (!enabled) return undefined
    const controller = new AbortController()
    setState((current) => ({ data: current.data, error: null, loading: true }))
    loadRef
      .current(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setState({ data, error: null, loading: false })
      })
      .catch((error) => {
        if (controller.signal.aborted || error?.name === 'AbortError') return
        setState((current) => ({ data: current.data, error, loading: false }))
      })
    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick, enabled])

  useEffect(() => {
    if (!pollMs || !enabled) return undefined
    const timer = setInterval(() => setTick((value) => value + 1), pollMs)
    return () => clearInterval(timer)
  }, [pollMs, enabled])

  const reload = useCallback(() => setTick((value) => value + 1), [])
  return { ...state, reload }
}
