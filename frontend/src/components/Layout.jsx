import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { Shield, AlertTriangle, Activity, Brain, Settings, Network, LogOut } from 'lucide-react'
import clsx from 'clsx'
import ErrorBoundary from './ErrorBoundary'
import { getUser, clearAuth } from '../lib/auth'
import { disconnectWebSocket } from '../lib/websocket'

const navItems = [
  { to: '/', icon: Activity, label: 'Overview' },
  { to: '/alerts', icon: AlertTriangle, label: 'Alerts' },
  { to: '/traffic', icon: Shield, label: 'Traffic' },
  { to: '/network', icon: Network, label: 'Network' },
  { to: '/ai-insights', icon: Brain, label: 'AI Insights' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export default function Layout() {
  const navigate = useNavigate()
  const user = getUser()

  function handleLogout() {
    disconnectWebSocket()
    clearAuth()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-900 text-white flex flex-col">
        <div className="p-4 border-b border-gray-700">
          <h1 className="text-xl font-bold flex items-center gap-2">
            <Shield className="w-6 h-6 text-blue-400" />
            Z-Sentinel
          </h1>
          <p className="text-xs text-gray-400 mt-1">IDS Monitoring Dashboard</p>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                )
              }
            >
              <Icon className="w-5 h-5" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-gray-700">
          {user && (
            <div className="mb-3">
              <p className="text-sm font-medium text-white truncate">{user.username}</p>
              <p className="text-xs text-gray-500 capitalize">{user.role}</p>
            </div>
          )}
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Đăng xuất
          </button>
          <p className="text-xs text-gray-600 mt-3">Z-Sentinel IDS v1.0.0</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto bg-gray-50">
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
      </main>
    </div>
  )
}
