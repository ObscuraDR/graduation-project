import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity, AlertTriangle, Shield, Server, Ban, Zap } from 'lucide-react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts'
import SeverityBadge from '../components/SeverityBadge'
import { fetchAlerts, fetchDashboardStats } from '../lib/api'
import { formatDatetime, formatChartHour } from '../lib/datetime'
import { onWebSocketMessage } from '../lib/websocket'

// Màu theo severity (cho các nơi khác dùng)
const SEVERITY_COLORS = {
  critical: '#ef4444',
  high:     '#f59e0b',
  medium:   '#3b82f6',
  low:      '#22c55e',
  default:  '#8b5cf6',
}

// Màu theo attack type (cho pie chart Loại tấn công)
const ATTACK_TYPE_COLORS = {
  DDoS:        '#ef4444',   // đỏ
  BruteForce:  '#f59e0b',   // vàng cam
  PortScan:    '#3b82f6',   // xanh dương
  Botnet:      '#a855f7',   // tím
  Abnormal:    '#f97316',   // cam
  Normal:      '#22c55e',   // xanh lá
  'Port Sweep':'#06b6d4',   // cyan
  'Suspicious User Behavior': '#ec4899', // hồng
  default:     '#64748b',   // xám
}

// Module-level cache
let _dashboardCache = null
let _recentAlertsCache = []
let _selectedHoursCache = 24  // nhớ lựa chọn khi chuyển tab

const TIME_RANGES = [
  { label: '24 giờ qua', hours: 24  },
  { label: '3 ngày qua', hours: 72  },
  { label: '7 ngày qua', hours: 168 },
]

// Format nhãn trục X theo khoảng thời gian
function formatXAxisTick(timeStr, hours) {
  if (!timeStr) return ''
  try {
    const d = new Date(timeStr)
    if (isNaN(d.getTime())) return timeStr

    if (hours <= 24) {
      // 24h → hiện giờ: "10:00", "11:00"
      return d.toLocaleTimeString('vi-VN', {
        hour: '2-digit', minute: '2-digit',
        timeZone: 'Asia/Ho_Chi_Minh', hour12: false
      })
    } else if (hours <= 72) {
      // 3 ngày → hiện ngày + giờ: "T6 10h", "T7 14h"
      const day = d.toLocaleDateString('vi-VN', { weekday: 'short', timeZone: 'Asia/Ho_Chi_Minh' })
      const hour = d.toLocaleTimeString('vi-VN', { hour: '2-digit', timeZone: 'Asia/Ho_Chi_Minh', hour12: false })
      return `${day} ${hour}`
    } else {
      // 7 ngày → hiện ngày trong tuần: "T2", "T3"
      return d.toLocaleDateString('vi-VN', { weekday: 'short', timeZone: 'Asia/Ho_Chi_Minh' })
    }
  } catch {
    return timeStr
  }
}

export default function Overview() {
  const [dashboard, setDashboard] = useState(_dashboardCache)
  const [recentAlerts, setRecentAlerts] = useState(_recentAlertsCache)
  const [isRefreshing, setIsRefreshing] = useState(!_dashboardCache)
  const [selectedHours, setSelectedHours] = useState(_selectedHoursCache)

  const loadDashboard = async (hours, silent = false) => {
    if (!silent) setIsRefreshing(true)
    try {
      const d = await fetchDashboardStats(hours)
      setDashboard(d)
      _dashboardCache = d
    } catch {}
    if (!silent) setIsRefreshing(false)
  }

  useEffect(() => {
    const loadAll = async () => {
      setIsRefreshing(true)
      const [d, a] = await Promise.allSettled([
        fetchDashboardStats(selectedHours),
        fetchAlerts({ limit: 8 }),
      ])
      if (d.status === 'fulfilled') { setDashboard(d.value); _dashboardCache = d.value }
      if (a.status === 'fulfilled') {
        const alertData = a.value
        const items = Array.isArray(alertData) ? alertData : (alertData?.items || [])
        setRecentAlerts(items)
        _recentAlertsCache = items
      }
      setIsRefreshing(false)
    }

    loadAll()

    const interval = setInterval(() => {
      loadDashboard(selectedHours, true)
    }, 30000)

    // Listen to real-time WebSocket alerts
    const unsubWs = onWebSocketMessage((msg) => {
      if (msg.type === 'alert' && msg.data) {
        const alertData = msg.data
        const formattedAlert = {
          alert_id: alertData.alert_id || String(Date.now()),
          attack_type: alertData.attack_type || 'Unknown Attack',
          source_ip: alertData.src_ip || alertData.source_ip || '—',
          dest_ip: alertData.dst_ip || alertData.dest_ip || '—',
          severity: alertData.severity || 'medium',
          timestamp: alertData.timestamp || new Date().toISOString(),
        }

        setRecentAlerts((prev) => {
          const filtered = prev.filter((a) => a.alert_id !== formattedAlert.alert_id)
          const updated = [formattedAlert, ...filtered].slice(0, 8)
          _recentAlertsCache = updated
          return updated
        })

        setDashboard((prev) => {
          if (!prev) return prev
          const updated = {
            ...prev,
            total_alerts: (prev.total_alerts || 0) + 1,
            active_alerts: (prev.active_alerts || 0) + 1,
            active_threats: (prev.active_threats || 0) + 1,
          }
          _dashboardCache = updated
          return updated
        })
      }
    })

    return () => {
      clearInterval(interval)
      unsubWs()
    }
  }, [selectedHours])

  const rangeLabel = TIME_RANGES.find(r => r.hours === selectedHours)?.label || '24 giờ qua'

  // KPI cards
  const kpis = [
    { title: 'Máy chủ', value: dashboard?.total_servers ?? '—', sub: 'đang quản lý', icon: Server, color: 'blue' },
    { title: 'Tổng cảnh báo', value: dashboard?.total_alerts ?? 0, sub: `${dashboard?.active_alerts ?? 0} đang hoạt động · ${rangeLabel}`, icon: AlertTriangle, color: 'red' },
    { title: 'IP bị chặn', value: dashboard?.blocked_ips ?? 0, sub: 'đang chặn', icon: Ban, color: 'amber' },
    { title: 'Mối đe dọa', value: dashboard?.active_threats ?? 0, sub: `cần xử lý · ${rangeLabel}`, icon: Shield, color: 'purple' },
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
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Tổng quan hệ thống</h1>
          <p className="text-sm text-slate-500 mt-0.5">Z-Sentinel IDS — Real-time Monitoring</p>
        </div>
        <div className="flex items-center gap-3">
          {/* Time range dropdown */}
          <select
            value={selectedHours}
            onChange={e => {
              const h = parseInt(e.target.value)
              setSelectedHours(h)
              _selectedHoursCache = h  // lưu cache
              loadDashboard(h)
            }}
            className="px-3 py-1.5 text-sm bg-slate-800 border border-slate-700 rounded-lg text-slate-300 focus:outline-none focus:border-blue-500 transition-colors"
          >
            {TIME_RANGES.map(r => (
              <option key={r.hours} value={r.hours}>{r.label}</option>
            ))}
          </select>

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
            <Activity className="w-4 h-4 text-red-400" /> Xu hướng tấn công ({rangeLabel})
          </h3>
          {(dashboard?.attack_trend?.length ?? 0) > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={dashboard.attack_trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#64748b' }} tickFormatter={(t) => formatXAxisTick(t, selectedHours)} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10, fill: '#64748b' }} allowDecimals={false} />
                <Tooltip
                  labelFormatter={(t) => formatXAxisTick(t, selectedHours)}
                  contentStyle={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '8px', color: '#1e293b', boxShadow: '0 4px 16px rgba(0,0,0,0.15)', fontSize: '13px' }}
                  wrapperStyle={{ outline: 'none', zIndex: 9999 }}
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
                      <Cell key={i} fill={ATTACK_TYPE_COLORS[entry.name] || ATTACK_TYPE_COLORS.default} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderColor: '#334155',
                      borderRadius: '10px',
                      color: '#ffffff',
                      boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.5)',
                      padding: '8px 12px',
                      fontSize: '13px',
                    }}
                    itemStyle={{ color: '#38bdf8', fontWeight: 600 }}
                    labelStyle={{ color: '#ffffff', fontWeight: 'bold' }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-1.5 mt-2">
                {pieData.slice(0, 4).map((item, i) => (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <span className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full" style={{ background: ATTACK_TYPE_COLORS[item.name] || ATTACK_TYPE_COLORS.default }} />
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
          <Link to="/alerts" className="text-xs text-blue-400 hover:text-blue-300 transition-colors">Xem tất cả →</Link>
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
