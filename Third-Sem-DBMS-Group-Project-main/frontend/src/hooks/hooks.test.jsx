import { act, renderHook, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { useAsync } from './useAsync.js'
import { useDebounce } from './useDebounce.js'
import { usePageTitle } from './usePageTitle.js'
import { useUrlState } from './useUrlState.js'

function deferred() {
  let resolve
  let reject
  const promise = new Promise((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('useAsync', () => {
  it('starts loading, then delivers the data', async () => {
    const { result } = renderHook(() => useAsync(async () => 'hello', []))
    expect(result.current).toMatchObject({ data: null, error: null, loading: true })
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current).toMatchObject({ data: 'hello', error: null })
  })

  it('reports a failure as an error with no data', async () => {
    const { result } = renderHook(() =>
      useAsync(async () => {
        throw new Error('boom')
      }, []),
    )
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.data).toBeNull()
    expect(result.current.error.message).toBe('boom')
  })

  it('keeps the previous data when a reload fails, and clears the error when it recovers', async () => {
    let failing = false
    const load = vi.fn(async () => {
      if (failing) throw new Error('down')
      return { version: load.mock.calls.length }
    })
    const { result } = renderHook(() => useAsync(load, []))
    await waitFor(() => expect(result.current.data).toEqual({ version: 1 }))

    failing = true
    act(() => result.current.reload())
    await waitFor(() => expect(result.current.error?.message).toBe('down'))
    expect(result.current.data).toEqual({ version: 1 })
    expect(result.current.loading).toBe(false)

    failing = false
    act(() => result.current.reload())
    await waitFor(() => expect(result.current.data).toEqual({ version: 3 }))
    expect(result.current.error).toBeNull()
  })

  it('aborts the previous request when its inputs change and ignores a late answer', async () => {
    const answers = { 1: deferred(), 2: deferred() }
    const signals = []
    const { result, rerender } = renderHook(
      ({ id }) =>
        useAsync((signal) => {
          signals.push(signal)
          return answers[id].promise
        }, [id]),
      { initialProps: { id: 1 } },
    )
    rerender({ id: 2 })
    expect(signals[0].aborted).toBe(true)
    expect(signals[1].aborted).toBe(false)

    await act(async () => {
      answers[2].resolve('second')
      answers[1].resolve('first (late)')
    })
    await waitFor(() => expect(result.current.data).toBe('second'))
    expect(result.current.data).toBe('second')
  })

  it('does not treat an aborted request as an error', async () => {
    const { result, rerender } = renderHook(
      ({ id }) =>
        useAsync(
          (signal) =>
            new Promise((_, reject) => {
              signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
            }),
          [id],
        ),
      { initialProps: { id: 1 } },
    )
    rerender({ id: 2 })
    await act(async () => {})
    expect(result.current.error).toBeNull()
  })

  it('does nothing while disabled and loads once enabled', async () => {
    const load = vi.fn(async () => 'ok')
    const { result, rerender } = renderHook(({ enabled }) => useAsync(load, [], { enabled }), {
      initialProps: { enabled: false },
    })
    expect(load).not.toHaveBeenCalled()
    expect(result.current).toMatchObject({ data: null, loading: false })
    rerender({ enabled: true })
    await waitFor(() => expect(result.current.data).toBe('ok'))
  })

  it('polls on an interval and stops when unmounted', async () => {
    vi.useFakeTimers()
    const load = vi.fn(async () => 'tick')
    const { unmount } = renderHook(() => useAsync(load, [], { pollMs: 1000 }))
    for (let second = 0; second < 3; second += 1) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000)
      })
    }
    expect(load).toHaveBeenCalledTimes(4)

    unmount()
    await vi.advanceTimersByTimeAsync(5000)
    expect(load).toHaveBeenCalledTimes(4)
  })
})

describe('useDebounce', () => {
  it('only passes on the latest value after the delay', () => {
    vi.useFakeTimers()
    const { result, rerender } = renderHook(({ value }) => useDebounce(value, 300), { initialProps: { value: 'a' } })
    expect(result.current).toBe('a')

    rerender({ value: 'ab' })
    rerender({ value: 'abc' })
    act(() => vi.advanceTimersByTime(299))
    expect(result.current).toBe('a')
    act(() => vi.advanceTimersByTime(1))
    expect(result.current).toBe('abc')
  })
})

describe('useUrlState', () => {
  const DEFAULTS = { search: '', status: '', page: '1' }
  const wrap =
    (url) =>
    ({ children }) => <MemoryRouter initialEntries={[url]}>{children}</MemoryRouter>

  it('reads values from the URL and falls back to the defaults', () => {
    const { result } = renderHook(() => useUrlState(DEFAULTS), { wrapper: wrap('/?search=lab&page=3') })
    expect(result.current[0]).toEqual({ search: 'lab', status: '', page: '3' })
  })

  it('updates the URL, and returns to page 1 when a filter changes', () => {
    const { result } = renderHook(() => useUrlState(DEFAULTS), { wrapper: wrap('/?page=4') })
    act(() => result.current[1]({ status: 'ACTIVE' }))
    expect(result.current[0]).toEqual({ search: '', status: 'ACTIVE', page: '1' })
  })

  it('keeps the page when only the page changes', () => {
    const { result } = renderHook(() => useUrlState(DEFAULTS), { wrapper: wrap('/?search=lab') })
    act(() => result.current[1]({ page: 3 }))
    expect(result.current[0]).toEqual({ search: 'lab', status: '', page: '3' })
  })

  it('removes a value from the URL when it is cleared or equals its default', () => {
    const { result } = renderHook(() => useUrlState(DEFAULTS), { wrapper: wrap('/?search=lab&status=ACTIVE') })
    act(() => result.current[1]({ search: '', status: 'ACTIVE' }))
    expect(result.current[0].search).toBe('')
    act(() => result.current[1]({ page: '1' }))
    expect(result.current[0].page).toBe('1')
  })

  it('applies several changes at once', () => {
    const { result } = renderHook(() => useUrlState(DEFAULTS), { wrapper: wrap('/') })
    act(() => result.current[1]({ search: 'a b', status: 'OFFLINE' }))
    expect(result.current[0]).toMatchObject({ search: 'a b', status: 'OFFLINE' })
  })
})

describe('usePageTitle', () => {
  it('puts the page name in the browser tab', () => {
    const { rerender } = renderHook(({ title }) => usePageTitle(title), { initialProps: { title: 'Nodes' } })
    expect(document.title).toBe('Nodes · NetMonitor')
    rerender({ title: 'Computer Lab A' })
    expect(document.title).toBe('Computer Lab A · NetMonitor')
  })
})
