import { useEffect, useState } from 'react'
import { Activity, AlertTriangle, Shield, Wifi, Server, Ban } from 'lucide-react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, BarChart, Bar,
} from 'recharts'
import SeverityBadge from '../components/SeverityBadge'
import {
  fetchHealthDetailed, fetchAlerts, fetchDashboardStats, fetchTrafficStats,
} from '../lib/api'
import { connectWebSocket, onWebSocketMessage } from '../lib/websocket'

const COLORS = ['#ef4444', '#f59e0b', '#3b82f6', '#22c55e', '#8b5cf6', '#ec4899']

export default function Overview() {
  const [health, setHealth] = useState(null)
  const [dashboard, setDashboard] = useState(null)
  const [recentAlerts, setRecentAlerts] = useState([])
  const [trafficData, setTrafficData] = useState([])
  const [liveAlerts, setLiveAlerts] = useState([])

  useEffect(() => {
    fetchHealthDetailed().then(setHealth).catch(console.error)
    fetchDashboardStats(24).then(setDashboard).catch(console.error)
    fetchAlerts({ limit: 5 }).then(setRecentAlerts).catch(console.error)

    // Fetch traffic stats ngay lập tức lần đầu
    fetchTrafficStats().then((data) => {
      setTrafficData([{
        time: new Date().toLocaleTimeString(),
        packets: data.pipeline?.processed_packets || 0,
        flows: data.flows?.active_flows || 0,
      }])
    }).catch(() => {})

    const interval = setInterval(() => {
      fetchTrafficStats().then((data) => {
        setTrafficData((prev) => {
          const point = {
            time: new Date().toLocaleTimeString(),
            packets: data.pipeline?.processed_packets || 0,
            flows: data.flows?.active_flows || 0,
          }
          return [...prev.slice(-30), point]
        })
      }).catch(() => {})
      fetchDashboardStats(24).then(setDashboard).catch(() => {})
    }, 30000)

    connectWebSocket()
    const unsub = onWebSocketMessage((msg) => {
      if (msg.type === 'alert') {
        setLiveAlerts((prev) => [msg.data, ...prev].slice(0, 10))
      }
    })

    return () => {
      clearInterval(interval)
      unsub()
      // Không disconnect WebSocket ở đây vì các trang khác có thể đang dùng
    }
  }, [])

  const severityData = dashboard?.threat_categories?.length
    ? dashboard.threat_categories.map((t) => ({ name: t.type, value: t.count }))
    : []

  const kpis = [
    {
      title: 'Servers',
      value: dashboard?.total_servers ?? '—',
      subtitle: 'Managed',
      icon: Server,
      color: '#3b82f6',
      bg: 'bg-blue-50',
    },
    {
      title: 'Total Alerts',
      value: dashboard?.total_alerts ?? 0,
      subtitle: `${dashboard?.active_alerts ?? 0} active`,
      icon: AlertTriangle,
      color: '#ef4444',
      bg: 'bg-red-50',
    },
    {
      title: 'Blocked IPs',
      value: dashboard?.blocked_ips ?? 0,
      subtitle: 'Active blocks',
      icon: Ban,
      color: '#f59e0b',
      bg: 'bg-yellow-50',
    },
    {
      title: 'Active Threats',
      value: dashboard?.active_threats ?? 0,
      subtitle: 'Needs attention',
      icon: Shield,
      color: '#8b5cf6',
      bg: 'bg-purple-50',
    },
  ]

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">System Overview</h1>
          <p className="text-sm text-gray-500">Real-time IDS monitoring dashboard</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`w-2.5 h-2.5 rounded-full ${health?.pipeline_running ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
          <span className="text-sm text-gray-600">
            {health?.pipeline_running ? 'Pipeline Running' : 'Pipeline Stopped'}
          </span>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 divide-y md:divide-y-0 md:divide-x md:flex">
        {kpis.map(({ title, value, subtitle, icon: Icon, color, bg }) => (
          <div key={title} className="flex-1 flex items-center gap-4 px-6 py-5">
            <div className={`p-3 rounded-xl ${bg} shrink-0`}>
              <Icon className="w-5 h-5" style={{ color }} />
            </div>
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{title}</p>
              <p className="text-2xl font-bold leading-tight" style={{ color }}>{value}</p>
              <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Attack Trend (24h)</h3>
          {(dashboard?.attack_trend?.length ?? 0) > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={dashboard.attack_trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="time" tick={{ fontSize: 10 }} tickFormatter={(v) => v?.slice(11, 16)} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Line type="monotone" dataKey="count" stroke="#ef4444" strokeWidth={2} dot={false} name="Alerts" />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-gray-400 text-sm">No attack data yet</div>
          )}
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Country Distribution</h3>
          {(dashboard?.country_distribution?.length ?? 0) > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={dashboard.country_distribution.slice(0, 8)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="country" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-gray-400 text-sm">No country data</div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Top Attack IPs</h3>
          <div className="space-y-2">
            {(dashboard?.top_attack_ips ?? []).slice(0, 8).map((row) => (
              <div key={row.ip} className="flex justify-between text-sm border-b border-gray-50 py-1.5">
                <span className="font-mono text-gray-800">{row.ip}</span>
                <span className="text-gray-500">{row.country} · {row.count}</span>
              </div>
            ))}
            {!dashboard?.top_attack_ips?.length && (
              <p className="text-sm text-gray-400">No data</p>
            )}
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Threat Categories</h3>
          {severityData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={severityData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} label>
                  {severityData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-gray-400 text-sm">No categories</div>
          )}
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4" /> Live Traffic
          </h3>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={trafficData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="time" tick={{ fontSize: 9 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip />
              <Line type="monotone" dataKey="flows" stroke="#22c55e" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Recent Alerts</h3>
          <div className="space-y-3">
            {recentAlerts.length > 0 ? recentAlerts.map((alert) => (
              <div key={alert.alert_id} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                <div>
                  <p className="text-sm font-medium text-gray-800">{alert.attack_type}</p>
                  <p className="text-xs text-gray-500">{alert.source_ip} → {alert.dest_ip}</p>
                </div>
                <SeverityBadge severity={alert.severity} />
              </div>
            )) : (
              <p className="text-sm text-gray-400">No alerts recorded</p>
            )}
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">
            <span className="inline-block w-2 h-2 bg-green-500 rounded-full animate-pulse mr-2" />
            Live Alert Feed
          </h3>
          <div className="space-y-3 max-h-[280px] overflow-y-auto">
            {liveAlerts.length > 0 ? liveAlerts.map((alert, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                <div>
                  <p className="text-sm font-medium text-gray-800">{alert.attack_type}</p>
                  <p className="text-xs text-gray-500">{alert.src_ip} · {alert.timestamp?.slice(11, 19)}</p>
                </div>
                <SeverityBadge severity={alert.severity} />
              </div>
            )) : (
              <p className="text-sm text-gray-400 italic">Waiting for alerts...</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
