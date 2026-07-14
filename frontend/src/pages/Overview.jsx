import { useEffect, useState } from 'react'
import { Activity, AlertTriangle, Shield, Server, Ban, Zap } from 'lucide-react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts'
import SeverityBadge from '../components/SeverityBadge'
import { fetchAlerts, fetchDashboardStats } from '../lib/api'
import { formatDatetime, formatChartHour } from '../lib/datetime'

const SEVERITY_COLORS = {
  critical: '#ef4444',
  high: '#f59e0b',
  medium: '#3b82f6',
  low: '#22c55e',
  default: '#8b5cf6',
}

// Module-level cache
let _dashboardCache = null
let _recentAlertsCache = []

export default function Overview() {
  const [dashboard, setDashboard] = useState(_dashboardCache)
  const [recentAlerts, setRecentAlerts] = useState(_recentAlertsCache)
  const [isRefreshing, setIsRefreshing] = useState(!_dashboardCache)

  useEffect(() => {
    const loadAll = async () => {
      setIsRefreshing(true)
      const [d, a] = await Promise.allSettled([
        fetchDashboardStats(24),
        fetchAlerts({ limit: 8 }),
      ])
      if (d.status === 'fulfilled') { setDashboard(d.value); _dashboardCache = d.value }
      if (a.status === 'fulfilled') { setRecentAlerts(a.value?.items || a.value || []); _recentAlertsCache = a.value?.items || a.value || [] }
      setIsRefreshing(false)
    }

    loadAll()

    const interval = setInterval(() => {
      fetchDashboardStats(24).then((d) => {
        setDashboard(d); _dashboardCache = d
      }).catch(() => {})
    }, 30000)

    return () => clearInterval(interval)
  }, [])

  // KPI cards
  const kpis = [
    { title: 'Máy chủ', value: dashboard?.total_servers ?? '—', sub: 'đang quản lý', icon: Server, color: 'blue' },
    { title: 'Tổng cảnh báo', value: dashboard?.total_alerts ?? 0, sub: `${dashboard?.active_alerts ?? 0} đang hoạt động`, icon: AlertTriangle, color: 'red' },
    { title: 'IP bị chặn', value: dashboard?.blocked_ips ?? 0, sub: 'đang chặn', icon: Ban, color: 'amber' },
    { title: 'Mối đe dọa', value: dashboard?.active_threats ?? 0, sub: 'cần xử lý', icon: Shield, color: 'purple' },
  ]

  const iconColorMap = {
    blue: { bg: 'bg-blue-500/10 border-blue-500/20', icon: 'text-blue-400', value: 'text-blue-400' },
    red: { bg: 'bg-red-500/10 border-red-500/20', icon: 'text-red-400', value: 'text-red-400' },
    amber: { bg: 'bg-amber-500/10 border-amber-500/20', icon: 'text-amber-400', value: 'text-amber-400' },
    purple: { bg: 'bg-violet-500/10 border-violet-500/20', icon: 'text-violet-400', value: 'text-violet-400' },
  }

  // Pie data từ threat_categories
  const pieData = (dashboard?.threat_categories ?? []).map((t) => ({ name: t.type, value: t.count }))

  return (
    <div className="space-y-5">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Tổng quan hệ thống</h1>
          <p className="text-sm text-slate-500 mt-0.5">Z-Sentinel IDS — Real-time Monitoring</p>
        </div>
        <div className="flex items-center gap-2">
          {isRefreshing && <span className="text-xs text-slate-500 animate-pulse">Đang tải...</span>}
          <span className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/20 rounded-full">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs text-emerald-400 font-medium">Hệ thống hoạt động</span>
          </span>
        </div>
      </div>

      {/* ── ROW 1: KPI Cards ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map(({ title, value, sub, icon: Icon, color }) => {
          const c = iconColorMap[color] || iconColorMap.blue
          return (
            <div key={title} className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 p-5 hover:border-slate-700/60 transition-all duration-200">
              <div className="flex items-center justify-between mb-3">
                <div className={`p-2.5 rounded-xl border ${c.bg}`}>
                  <Icon className={`w-5 h-5 ${c.icon}`} />
                </div>
              </div>
              <p className="text-xs text-slate-500 uppercase tracking-wider font-medium">{title}</p>
              <p className={`text-3xl font-bold mt-1 ${c.value}`}>{value}</p>
              <p className="text-xs text-slate-600 mt-1">{sub}</p>
            </div>
          )
        })}
      </div>

      {/* ── ROW 2: Attack Trend + Threat Pie ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Attack Trend — chiếm 2/3 */}
        <div className="lg:col-span-2 bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4 text-red-400" /> Xu hướng tấn công (24h)
          </h3>
          {(dashboard?.attack_trend?.length ?? 0) > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={dashboard.attack_trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#64748b' }} tickFormatter={formatChartHour} />
                <YAxis tick={{ fontSize: 10, fill: '#64748b' }} allowDecimals={false} />
                <Tooltip
                  labelFormatter={formatChartHour}
                  contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '8px', color: '#e2e8f0' }}
                />
                <Line
                  type="monotone" dataKey="count" stroke="#ef4444"
                  strokeWidth={2} dot={false} name="Cảnh báo"
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[180px] flex flex-col items-center justify-center text-slate-600 gap-2">
              <Activity className="w-8 h-8" />
              <span className="text-sm">Chưa có dữ liệu tấn công</span>
            </div>
          )}
        </div>

        {/* Threat Categories Pie — chiếm 1/3 */}
        <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
            <Zap className="w-4 h-4 text-violet-400" /> Loại tấn công
          </h3>
          {pieData.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={140}>
                <PieChart>
                  <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={60} innerRadius={30}>
                    {pieData.map((entry, i) => (
                      <Cell key={i} fill={SEVERITY_COLORS[entry.name] || SEVERITY_COLORS.default} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '8px', color: '#e2e8f0' }} />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-1.5 mt-2">
                {pieData.slice(0, 4).map((item, i) => (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <span className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full" style={{ background: SEVERITY_COLORS[item.name] || SEVERITY_COLORS.default }} />
                      <span className="text-slate-400">{item.name}</span>
                    </span>
                    <span className="font-semibold text-slate-300">{item.value}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="h-[180px] flex flex-col items-center justify-center text-slate-600 gap-2">
              <Zap className="w-8 h-8" />
              <span className="text-sm">Chưa có dữ liệu</span>
            </div>
          )}
        </div>
      </div>

      {/* ── ROW 3: Recent Alerts (full width) ── */}
      <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-slate-300">Cảnh báo gần đây</h3>
          <a href="/alerts" className="text-xs text-blue-400 hover:text-blue-300 transition-colors">Xem tất cả →</a>
        </div>
        <div className="space-y-2 max-h-[220px] overflow-y-auto">
          {recentAlerts.length > 0 ? recentAlerts.map((alert) => (
            <div key={alert.alert_id} className="flex items-center justify-between py-2.5 px-3 rounded-lg border border-slate-800/60 hover:bg-slate-800/40 transition-colors">
              <div className="min-w-0 flex-1 mr-2">
                <p className="text-sm font-medium text-slate-200 truncate">{alert.attack_type}</p>
                <p className="text-xs text-slate-500 truncate">
                  {alert.source_ip} → {alert.dest_ip} · {formatDatetime(alert.timestamp)}
                </p>
              </div>
              <SeverityBadge severity={alert.severity} />
            </div>
          )) : (
            <div className="h-[160px] flex flex-col items-center justify-center text-slate-600 gap-2">
              <AlertTriangle className="w-8 h-8" />
              <span className="text-sm">Chưa có cảnh báo</span>
            </div>
          )}
        </div>
      </div>

    </div>
  )
}
