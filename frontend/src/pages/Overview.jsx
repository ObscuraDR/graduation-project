import { useEffect, useState } from 'react'
import { Activity, AlertTriangle, Shield, Wifi } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import StatCard from '../components/StatCard'
import SeverityBadge from '../components/SeverityBadge'
import { fetchHealthDetailed, fetchAlerts, fetchSystemStats, fetchTrafficStats } from '../lib/api'
import { connectWebSocket, onWebSocketMessage } from '../lib/websocket'

const COLORS = ['#ef4444', '#f59e0b', '#3b82f6', '#22c55e', '#8b5cf6']

export default function Overview() {
  const [health, setHealth] = useState(null)
  const [stats, setStats] = useState(null)
  const [recentAlerts, setRecentAlerts] = useState([])
  const [trafficData, setTrafficData] = useState([])
  const [liveAlerts, setLiveAlerts] = useState([])

  useEffect(() => {
    // Fetch initial data
    fetchHealthDetailed().then(setHealth).catch(console.error)
    fetchSystemStats().then(setStats).catch(console.error)
    fetchAlerts({ limit: 5 }).then(setRecentAlerts).catch(console.error)

    // Poll traffic stats every 5s
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
    }, 5000)

    // WebSocket for live alerts
    connectWebSocket()
    const unsub = onWebSocketMessage((msg) => {
      if (msg.type === 'alert') {
        setLiveAlerts((prev) => [msg.data, ...prev].slice(0, 10))
      }
    })

    return () => {
      clearInterval(interval)
      unsub()
    }
  }, [])

  const severityData = stats?.alerts_by_severity
    ? Object.entries(stats.alerts_by_severity).map(([name, value]) => ({ name, value }))
    : []

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
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

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Alerts"
          value={stats?.total_alerts || 0}
          subtitle={`${stats?.active_alerts || 0} active`}
          icon={AlertTriangle}
          color="red"
        />
        <StatCard
          title="Active Flows"
          value={trafficData.length > 0 ? trafficData[trafficData.length - 1].flows : 0}
          subtitle="In memory"
          icon={Activity}
          color="blue"
        />
        <StatCard
          title="Services"
          value={health ? [health.postgres?.connected, health.redis?.connected, health.mongo?.connected].filter(Boolean).length : 0}
          subtitle="of 3 connected"
          icon={Wifi}
          color="green"
        />
        <StatCard
          title="Model Status"
          value={health?.model_loaded ? 'Loaded' : 'Not Loaded'}
          subtitle="Ensemble classifier"
          icon={Shield}
          color={health?.model_loaded ? 'green' : 'yellow'}
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Traffic Chart */}
        <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Live Traffic</h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={trafficData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="time" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line type="monotone" dataKey="packets" stroke="#3b82f6" strokeWidth={2} dot={false} name="Packets" />
              <Line type="monotone" dataKey="flows" stroke="#22c55e" strokeWidth={2} dot={false} name="Flows" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Severity Distribution */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Alert Severity</h3>
          {severityData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie data={severityData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                  {severityData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[250px] text-gray-400 text-sm">No alerts yet</div>
          )}
        </div>
      </div>

      {/* Recent Alerts + Live Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Alerts from DB */}
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

        {/* Live WebSocket Feed */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">
            <span className="inline-block w-2 h-2 bg-green-500 rounded-full animate-pulse mr-2" />
            Live Alert Feed
          </h3>
          <div className="space-y-3 max-h-[300px] overflow-y-auto">
            {liveAlerts.length > 0 ? liveAlerts.map((alert, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                <div>
                  <p className="text-sm font-medium text-gray-800">{alert.attack_type}</p>
                  <p className="text-xs text-gray-500">{alert.src_ip} • {alert.timestamp?.slice(11, 19)}</p>
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
