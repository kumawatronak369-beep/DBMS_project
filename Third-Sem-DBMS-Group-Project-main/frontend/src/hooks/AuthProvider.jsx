import { useCallback, useEffect, useMemo, useState } from 'react'
import { setAuthToken, setUnauthorizedHandler } from '../services/api.js'
import * as authService from '../services/auth.js'
import { AuthContext } from './AuthContext.js'

const STORAGE_KEY = 'nm.session'

function readStoredSession() {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null')
    if (stored?.token && stored.expiresAt > Date.now()) return stored
  } catch {
    /* unreadable or unavailable storage: treat as signed out */
  }
  return null
}

function writeStoredSession(session) {
  try {
    if (session) localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    /* storage unavailable: the session simply will not survive a refresh */
  }
}

export function AuthProvider({ children }) {
  const [session, setSession] = useState(() => {
    const stored = readStoredSession()
    setAuthToken(stored?.token ?? null)
    return stored
  })
  const [checking, setChecking] = useState(Boolean(session))
  const [sessionExpired, setSessionExpired] = useState(false)

  const clearSession = useCallback(() => {
    setAuthToken(null)
    writeStoredSession(null)
    setSession(null)
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(() => {
      clearSession()
      setSessionExpired(true)
    })
    return () => setUnauthorizedHandler(null)
  }, [clearSession])

  useEffect(() => {
    if (!session) {
      setChecking(false)
      return undefined
    }
    const controller = new AbortController()
    authService
      .getCurrentUser(controller.signal)
      .then((user) => {
        setSession((current) => {
          const next = current ? { ...current, user } : current
          writeStoredSession(next)
          return next
        })
      })
      .catch(() => {
        /* a 401 is handled by the unauthorized handler; a network error keeps the session */
      })
      .finally(() => {
        if (!controller.signal.aborted) setChecking(false)
      })
    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const login = useCallback(async (email, password) => {
    const result = await authService.login(email, password)
    const next = {
      token: result.access_token,
      user: result.user,
      expiresAt: Date.now() + result.expires_in * 1000,
    }
    setAuthToken(next.token)
    writeStoredSession(next)
    setSessionExpired(false)
    setSession(next)
    return result.user
  }, [])

  const logout = useCallback(async () => {
    try {
      await authService.logout()
    } catch {
      /* the token is discarded either way */
    }
    clearSession()
    setSessionExpired(false)
  }, [clearSession])

  const value = useMemo(
    () => ({
      user: session?.user ?? null,
      expiresAt: session?.expiresAt ?? null,
      isAuthenticated: Boolean(session),
      isAdmin: session?.user?.role === 'ADMIN',
      checking,
      sessionExpired,
      login,
      logout,
    }),
    [session, checking, sessionExpired, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
