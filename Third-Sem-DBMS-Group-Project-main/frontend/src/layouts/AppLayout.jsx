import {
  BarChart3,
  ChevronDown,
  FlaskConical,
  Globe,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  MonitorSmartphone,
  Network,
  Settings,
  Users,
  X,
} from 'lucide-react'
import { Suspense, useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { HealthDots } from '../components/HealthIndicators.jsx'
import { SkeletonRows } from '../components/ui/States.jsx'
import { Badge } from '../components/ui/StatusBadge.jsx'
import { useAuth } from '../hooks/useAuth.js'
import { useHealth } from '../hooks/useHealth.js'
import { titleCase } from '../utils/status.js'

const MAIN_NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/nodes', label: 'Nodes', icon: Network },
  { to: '/devices', label: 'Devices', icon: MonitorSmartphone },
  { to: '/destinations', label: 'Destinations', icon: Globe },
  { to: '/history', label: 'Network History', icon: History },
  { to: '/reports', label: 'Reports', icon: BarChart3 },
]

// the demo runs on generated events; set VITE_SIMULATED_DATA=false to hide the badge
const SHOW_SIMULATED_BADGE = import.meta.env.VITE_SIMULATED_DATA !== 'false'

function NavItem({ to, label, icon: Icon }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `group flex items-center gap-2.5 rounded-md border-l-2 px-3 py-2 text-[13px] transition-colors ${
          isActive
            ? 'border-accent bg-accent/10 text-ink'
            : 'border-transparent text-muted hover:bg-panel-2 hover:text-ink'
        }`
      }
    >
      <Icon size={16} className="shrink-0" aria-hidden="true" />
      {label}
    </NavLink>
  )
}

function Brand() {
  return (
    <div className="flex h-14 items-center gap-2.5 border-b border-line px-4">
      <span className="flex size-7 items-center justify-center rounded-md bg-accent/15 text-accent">
        <Network size={16} aria-hidden="true" />
      </span>
      <div className="leading-tight">
        <p className="text-sm font-semibold tracking-tight text-ink">NetMonitor</p>
        <p className="text-[10px] uppercase tracking-wider text-muted">Network operations</p>
      </div>
    </div>
  )
}

function UserMenu() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    const onPointerDown = (event) => {
      if (!ref.current?.contains(event.target)) setOpen(false)
    }
    const onKeyDown = (event) => event.key === 'Escape' && setOpen(false)
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  const initials = (user?.name ?? '?')
    .split(/\s+/)
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-2 rounded-md px-2 py-1 transition-colors hover:bg-panel-2"
      >
        <span className="flex size-7 items-center justify-center rounded-full bg-accent/20 text-[11px] font-semibold text-accent">
          {initials}
        </span>
        <span className="hidden text-left leading-tight sm:block">
          <span className="block text-[13px] text-ink">{user?.name}</span>
          <span className="block text-[11px] text-muted">{titleCase(user?.role)}</span>
        </span>
        <ChevronDown size={14} className="text-muted" aria-hidden="true" />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 z-40 mt-1 w-60 rounded-md border border-line-strong bg-panel py-1 shadow-xl"
        >
          <div className="border-b border-line px-3 py-2">
            <p className="truncate text-[13px] font-medium text-ink">{user?.name}</p>
            <p className="truncate text-xs text-muted">{user?.email}</p>
            <div className="mt-1.5">
              <Badge tone={user?.role === 'ADMIN' ? 'accent' : 'neutral'}>{titleCase(user?.role)}</Badge>
            </div>
          </div>
          <NavLink
            to="/settings"
            role="menuitem"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 px-3 py-2 text-[13px] text-muted transition-colors hover:bg-panel-2 hover:text-ink"
          >
            <Settings size={14} aria-hidden="true" /> Settings
          </NavLink>
          <button
            type="button"
            role="menuitem"
            onClick={logout}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-[13px] text-muted transition-colors hover:bg-panel-2 hover:text-ink"
          >
            <LogOut size={14} aria-hidden="true" /> Sign out
          </button>
        </div>
      )}
    </div>
  )
}

export default function AppLayout() {
  const { isAdmin } = useAuth()
  const health = useHealth()
  const location = useLocation()
  const [navOpenPath, setNavOpenPath] = useState(null)
  const navOpen = navOpenPath === location.pathname
  const setNavOpen = (open) => setNavOpenPath(open ? location.pathname : null)

  const sidebar = (
    <>
      <Brand />
      <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto p-3" aria-label="Main navigation">
        {MAIN_NAV.map((item) => (
          <NavItem key={item.to} {...item} />
        ))}
        <div className="mt-auto flex flex-col gap-0.5 border-t border-line pt-3">
          {isAdmin && <NavItem to="/users" label="Users" icon={Users} />}
          <NavItem to="/settings" label="Settings" icon={Settings} />
        </div>
      </nav>
      <div className="border-t border-line px-4 py-3">
        <HealthDots health={health} />
      </div>
    </>
  )

  return (
    <div className="flex h-full">
      {/* Desktop sidebar */}
      <aside className="hidden w-56 shrink-0 flex-col border-r border-line bg-panel lg:flex">{sidebar}</aside>

      {/* Mobile drawer */}
      {navOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setNavOpen(false)} aria-hidden="true" />
          <aside className="relative flex h-full w-64 flex-col border-r border-line bg-panel shadow-2xl">
            <button
              type="button"
              onClick={() => setNavOpen(false)}
              aria-label="Close navigation"
              className="absolute right-2 top-3 rounded-md p-1.5 text-muted hover:bg-panel-2 hover:text-ink"
            >
              <X size={16} />
            </button>
            {sidebar}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-line bg-panel px-4 lg:px-6">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setNavOpen(true)}
              aria-label="Open navigation"
              className="rounded-md p-1.5 text-muted hover:bg-panel-2 hover:text-ink lg:hidden"
            >
              <Menu size={18} />
            </button>
            {SHOW_SIMULATED_BADGE && (
              <span
                className="inline-flex items-center gap-1.5 rounded border border-warn/30 bg-warn/10 px-2 py-0.5 text-[11px] font-medium text-warn"
                title="Network events in this environment are generated for demonstration"
              >
                <FlaskConical size={12} aria-hidden="true" />
                <span className="hidden sm:inline">Simulated demo data</span>
                <span className="sm:hidden">Demo data</span>
              </span>
            )}
          </div>
          <UserMenu />
        </header>

        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[1500px] p-4 lg:p-6">
            <Suspense fallback={<SkeletonRows rows={8} />}>
              <Outlet />
            </Suspense>
          </div>
        </main>
      </div>
    </div>
  )
}
