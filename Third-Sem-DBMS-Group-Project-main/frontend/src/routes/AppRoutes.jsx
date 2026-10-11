import { lazy } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from '../layouts/AppLayout.jsx'
import LoginPage from '../pages/LoginPage.jsx'
import { RequireAdmin, RequireAuth } from './guards.jsx'

// pages load on demand so the charts aren't in the first download
const DashboardPage = lazy(() => import('../pages/DashboardPage.jsx'))
const DestinationDetailPage = lazy(() => import('../pages/DestinationDetailPage.jsx'))
const DestinationsPage = lazy(() => import('../pages/DestinationsPage.jsx'))
const DeviceDetailPage = lazy(() => import('../pages/DeviceDetailPage.jsx'))
const DevicesPage = lazy(() => import('../pages/DevicesPage.jsx'))
const HistoryPage = lazy(() => import('../pages/HistoryPage.jsx'))
const NodeDetailPage = lazy(() => import('../pages/NodeDetailPage.jsx'))
const NodesPage = lazy(() => import('../pages/NodesPage.jsx'))
const NotFoundPage = lazy(() => import('../pages/NotFoundPage.jsx'))
const ReportsPage = lazy(() => import('../pages/ReportsPage.jsx'))
const SettingsPage = lazy(() => import('../pages/SettingsPage.jsx'))
const UsersPage = lazy(() => import('../pages/UsersPage.jsx'))

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<RequireAuth />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/nodes" element={<NodesPage />} />
          <Route path="/nodes/:id" element={<NodeDetailPage />} />
          <Route path="/devices" element={<DevicesPage />} />
          <Route path="/devices/:id" element={<DeviceDetailPage />} />
          <Route path="/destinations" element={<DestinationsPage />} />
          <Route path="/destinations/:id" element={<DestinationDetailPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route element={<RequireAdmin />}>
            <Route path="/users" element={<UsersPage />} />
          </Route>
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  )
}
