import { Loader2, ShieldAlert } from 'lucide-react'
import { Link, Navigate, Outlet, useLocation } from 'react-router-dom'
import { EmptyState } from '../components/ui/States.jsx'
import { Button } from '../components/ui/Button.jsx'
import { useAuth } from '../hooks/useAuth.js'

// signed-in users only (the backend enforces this too)
export function RequireAuth() {
  const { isAuthenticated, checking } = useAuth()
  const location = useLocation()

  if (checking) {
    return (
      <div className="flex h-full items-center justify-center text-muted" role="status" aria-label="Checking your session">
        <Loader2 className="animate-spin" size={20} />
      </div>
    )
  }
  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: location }} />
  return <Outlet />
}

// admin only; the API returns 403 for analysts regardless
export function RequireAdmin() {
  const { isAdmin } = useAuth()
  if (isAdmin) return <Outlet />
  return (
    <EmptyState
      icon={ShieldAlert}
      title="Administrators only"
      hint="Your account does not have permission to view this page."
      action={
        <Link to="/dashboard">
          <Button>Back to dashboard</Button>
        </Link>
      }
    />
  )
}
