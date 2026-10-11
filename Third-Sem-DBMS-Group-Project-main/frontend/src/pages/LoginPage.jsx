import { AlertTriangle, LogIn, Network } from 'lucide-react'
import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Button } from '../components/ui/Button.jsx'
import { Field, TextInput } from '../components/ui/Fields.jsx'
import { useAuth } from '../hooks/useAuth.js'
import { usePageTitle } from '../hooks/usePageTitle.js'

// shown only in development builds
const DEMO_ACCOUNTS = import.meta.env.DEV
  ? [
      { label: 'Administrator', email: 'admin@netmonitor.local', password: 'Admin@12345' },
      { label: 'Analyst', email: 'analyst@netmonitor.local', password: 'Analyst@12345' },
    ]
  : []

export default function LoginPage() {
  usePageTitle('Sign in')
  const { isAuthenticated, login, sessionExpired } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const destination = location.state?.from?.pathname ?? '/dashboard'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [pending, setPending] = useState(false)

  if (isAuthenticated) return <Navigate to={destination} replace />

  async function handleSubmit(event) {
    event.preventDefault()
    if (!email.trim() || !password) {
      setError('Enter your email and password.')
      return
    }
    setPending(true)
    setError(null)
    try {
      await login(email.trim(), password)
      navigate(destination, { replace: true })
    } catch (err) {
      setError(err.message)
      setPending(false)
    }
  }

  return (
    <div className="flex min-h-full items-center justify-center bg-surface p-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center text-center">
          <span className="mb-3 flex size-11 items-center justify-center rounded-lg bg-accent/15 text-accent">
            <Network size={22} aria-hidden="true" />
          </span>
          <h1 className="text-lg font-semibold tracking-tight text-ink">NetMonitor</h1>
          <p className="mt-1 text-sm text-muted">Private network monitoring for authorized administrators</p>
        </div>

        <form onSubmit={handleSubmit} noValidate className="space-y-4 rounded-lg border border-line bg-panel p-5">
          {sessionExpired && !error && (
            <p className="flex items-start gap-2 rounded-md border border-warn/30 bg-warn/10 px-3 py-2 text-xs text-warn" role="status">
              <AlertTriangle size={14} className="mt-px shrink-0" aria-hidden="true" />
              Your session has ended. Please sign in again.
            </p>
          )}
          {error && (
            <p className="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger" role="alert">
              {error}
            </p>
          )}

          <Field label="Email">
            {(id) => (
              <TextInput
                id={id}
                type="email"
                autoComplete="username"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoFocus
              />
            )}
          </Field>
          <Field label="Password">
            {(id) => (
              <TextInput
                id={id}
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            )}
          </Field>

          <Button type="submit" variant="primary" icon={LogIn} loading={pending} className="w-full">
            Sign in
          </Button>
        </form>

        {DEMO_ACCOUNTS.length > 0 && (
          <div className="mt-4 rounded-lg border border-dashed border-line-strong p-3 text-xs text-muted">
            <p className="mb-2 font-medium text-ink/80">Demo accounts (development build)</p>
            <div className="space-y-1.5">
              {DEMO_ACCOUNTS.map((account) => (
                <button
                  key={account.email}
                  type="button"
                  onClick={() => {
                    setEmail(account.email)
                    setPassword(account.password)
                    setError(null)
                  }}
                  className="flex w-full items-center justify-between rounded px-2 py-1.5 text-left transition-colors hover:bg-panel-2"
                >
                  <span>{account.label}</span>
                  <span className="font-mono text-[11px] text-faint">{account.email}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
