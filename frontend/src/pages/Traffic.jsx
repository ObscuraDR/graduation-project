import { useEffect, useState, useCallback } from 'react'
import { Activity, RefreshCw, Play, Pause, Network, Filter, Zap, Radio, Square, ChevronDown } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell
} from 'recharts'
import {
  fetchActiveFlows, fetchTopTalkers, fetchTrafficStats,
  startSniffer, stopSniffer, fetchSnifferStatus, fetchInterfaces,
} from '../lib/api'

const PROTOCOL_COLORS = {
  tcp:     '#3b82f6',
  udp:     '#22c55e',
  icmp:    '#f59e0b',
  unknown: '#64748b',
}

const CHART_STYLE = {
  backgroundColor: '#0f172a',
  borderColor: '#334155',
  borderRadius: '10px',
  color: '#ffffff',
  boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.5)',
  padding: '8px 12px',
  fontSize: '13px',
}

const CHART_ITEM_STYLE = {
  color: '#38bdf8',
  fontWeight: 600,
}

const CHART_LABEL_STYLE = {
  color: '#ffffff',
  fontWeight: 'bold',
}

const CHART_WRAPPER_STYLE = {
  outline: 'none',
  zIndex: 9999,
}

let _trafficCache = null
let _interfacesCache = []
let _selectedIfaceCache = ''
let _refreshIntervalCache = 5   // nhớ interval khi chuyển tab
let _filterProtoCache = ''      // nhớ filter protocol khi chuyển tab

export default function Traffic() {
  const [flows, setFlows] = useState(_trafficCache?.flows || [])
  const [topTalkers, setTopTalkers] = useState(_trafficCache?.topTalkers || [])
  const [stats, setStats] = useState(_trafficCache?.stats || null)
  const [loading, setLoading] = useState(!_trafficCache)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [refreshInterval, setRefreshInterval] = useState(_refreshIntervalCache)
  const [filterProto, setFilterProto] = useState(_filterProtoCache)
  const [trafficHistory, setTrafficHistory] = useState([])

  // ── Sniffer controls ──────────────────────────────────────────────────────
  const [snifferRunning, setSnifferRunning] = useState(false)
  const [snifferLoading, setSnifferLoading] = useState(false)
  const [snifferError, setSnifferError] = useState(null)
  const [interfaces, setInterfaces] = useState(_interfacesCache)
  const [selectedIface, setSelectedIface] = useState(_selectedIfaceCache)

  // Load available interfaces on mount — dùng cache nếu đã có
  useEffect(() => {
    if (_interfacesCache.length > 0) return  // đã có cache → không fetch lại

    fetchInterfaces()
      .then(data => {
        const ifaces = data.interfaces || []
        _interfacesCache = ifaces

        // Ưu tiên chọn Wi-Fi, nếu không có thì chọn cái đầu tiên
        const preferred = ifaces.find(i =>
          i.toLowerCase().includes('wi-fi') ||
          i.toLowerCase().includes('wifi') ||
          i.toLowerCase().includes('wlan') ||
          i.toLowerCase().includes('eth0')
        ) || ifaces[0] || ''

        _selectedIfaceCache = preferred
        setInterfaces(ifaces)
        setSelectedIface(preferred)
      })
      .catch(() => {})
  }, [])

  // Poll sniffer status every 5s
  useEffect(() => {
    const poll = async () => {
      try {
        const s = await fetchSnifferStatus()
        setSnifferRunning(s.is_running === true)
      } catch {}
    }
    poll()
    const id = setInterval(poll, 5000)
    return () => clearInterval(id)
  }, [])

  const handleStartSniffer = useCallback(async () => {
    if (!selectedIface) return
    setSnifferLoading(true)
    setSnifferError(null)
    try {
      const res = await startSniffer({ interface: selectedIface })
      if (res?.status === 'error') {
        setSnifferError(res.message || 'Không thể khởi động sniffer')
      } else {
        setSnifferRunning(true)
      }
    } catch (err) {
      const detail = err?.response?.data?.detail
      if (typeof detail === 'object') {
        setSnifferError(`Interface không hợp lệ. Các interface có sẵn: ${(detail.available_interfaces || []).join(', ')}`)
      } else {
        setSnifferError(detail || 'Không thể khởi động sniffer')
      }
    }
    setSnifferLoading(false)
  }, [selectedIface])

  const handleStopSniffer = useCallback(async () => {
    setSnifferLoading(true)
    setSnifferError(null)
    try {
      const res = await stopSniffer()
      // Backend trả 200 nhưng status:"error" khi không có sniffer đang chạy
      if (res?.status === 'error') {
        // Sniffer không chạy trên backend → đồng bộ lại state về false
        setSnifferRunning(false)
        setSnifferError(null) // không hiện lỗi vì đây là trạng thái đúng
      } else {
        setSnifferRunning(false)
      }
    } catch (err) {
      // HTTP error → sync lại trạng thái thực từ backend
      try {
        const s = await fetchSnifferStatus()
        setSnifferRunning(s.is_running === true)
      } catch {}
      setSnifferError(err?.response?.data?.detail || 'Không thể dừng sniffer')
    }
    setSnifferLoading(false)
  }, [])

  const loadData = async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const [flowsData, talkersData, statsData] = await Promise.all([
        fetchActiveFlows(200),
        fetchTopTalkers(10),
        fetchTrafficStats(),
      ])
      setFlows(flowsData)
      setTopTalkers(talkersData)
      setStats(statsData)
      _trafficCache = { flows: flowsData, topTalkers: talkersData, stats: statsData }

      // Cập nhật lịch sử traffic
      setTrafficHistory(prev => {
        const point = {
          time: new Date().toLocaleTimeString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }),
          flows: statsData?.flows?.active_flows || 0,
          packets: statsData?.pipeline?.processed_packets || 0,
        }
        return [...prev.slice(-20), point]
      })
    } catch (err) {
      console.error('Failed to load traffic data:', err)
    }
    if (!silent) setLoading(false)
  }

  useEffect(() => {
    loadData()
  }, [])

  useEffect(() => {
    if (!autoRefresh) return
    // silent=true để không gây flash UI khi auto-refresh nền
    const interval = setInterval(() => loadData(true), refreshInterval * 1000)
    return () => clearInterval(interval)
  }, [autoRefresh, refreshInterval])

  // Protocol distribution
  const protocolStats = flows.reduce((acc, flow) => {
    const proto = String(flow.protocol ?? 'unknown').toLowerCase()
    if (!acc[proto]) acc[proto] = { name: proto, count: 0, packets: 0, bytes: 0 }
    acc[proto].count   += 1
    acc[proto].packets += flow.packet_count || 0
    acc[proto].bytes   += flow.byte_count || 0
    return acc
  }, {})
  const protocolData = Object.values(protocolStats)

  // Top destination ports
  const portStats = flows.reduce((acc, flow) => {
    if (!flow.dst_port) return acc
    const k = String(flow.dst_port)
    if (!acc[k]) acc[k] = { port: flow.dst_port, count: 0 }
    acc[k].count += 1
    return acc
  }, {})
  const topPorts = Object.values(portStats).sort((a, b) => b.count - a.count).slice(0, 10)

  const filteredFlows = filterProto
    ? flows.filter(f => String(f.protocol ?? '').toLowerCase() === filterProto)
    : flows

  return (
    <div className="p-6 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-blue-500/10 border border-blue-500/20">
            <Network className="w-6 h-6 text-blue-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-100">Phân tích Lưu lượng</h1>
            <p className="text-sm text-slate-500 mt-0.5">
              {flows.length} flows đang theo dõi
              {stats?.pipeline?.is_running && (
                <span className="ml-2 text-green-400 text-xs">● Pipeline đang chạy</span>
              )}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {autoRefresh && (
            <select value={refreshInterval}
              onChange={e => {
                const v = parseInt(e.target.value)
                setRefreshInterval(v)
                _refreshIntervalCache = v
              }}
              className="px-2 py-1.5 text-xs bg-slate-800 border border-slate-700 rounded-lg text-slate-300">
              <option value={5}>5s</option>
              <option value={10}>10s</option>
              <option value={30}>30s</option>
            </select>
          )}
          <button onClick={() => setAutoRefresh(!autoRefresh)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm border transition-colors ${
              autoRefresh ? 'bg-green-600 border-green-600 text-white' : 'bg-slate-800 border-slate-700 text-slate-300'
            }`}>
            {autoRefresh ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            {autoRefresh ? 'Live' : 'Pause'}
          </button>
          <button onClick={loadData} disabled={loading}
            className="p-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-300 hover:bg-slate-700 disabled:opacity-50">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Sniffer Control Panel */}
      <div className={`rounded-xl border p-4 ${snifferRunning ? 'bg-green-950/30 border-green-700/40' : 'bg-slate-900/60 border-slate-800/60'}`}>
        <div className="flex flex-wrap items-center gap-3">
          {/* Status indicator */}
          <div className="flex items-center gap-2 mr-2">
            <span className={`w-2.5 h-2.5 rounded-full ${snifferRunning ? 'bg-green-400 animate-pulse' : 'bg-slate-600'}`} />
            <span className="text-sm font-semibold text-slate-200">
              {snifferRunning ? 'Đang bắt gói tin' : 'Sniffer đang tắt'}
            </span>
          </div>

          {/* Interface selector */}
          <div className="flex items-center gap-2">
            <ChevronDown className="w-4 h-4 text-slate-500" />
            <select
              value={selectedIface}
              onChange={e => {
                setSelectedIface(e.target.value)
                _selectedIfaceCache = e.target.value  // lưu cache
              }}
              disabled={snifferRunning || snifferLoading}
              className="px-3 py-1.5 text-xs bg-slate-800 border border-slate-700 rounded-lg text-slate-300 disabled:opacity-50 max-w-xs"
            >
              {interfaces.length === 0
                ? <option value="">Đang tải interface...</option>
                : interfaces.map(iface => <option key={iface} value={iface}>{iface}</option>)
              }
            </select>
          </div>

          {/* Start / Stop button */}
          {snifferRunning ? (
            <button
              onClick={handleStopSniffer}
              disabled={snifferLoading}
              className="flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-medium bg-red-600 hover:bg-red-700 text-white disabled:opacity-50 transition-colors"
            >
              <Square className="w-4 h-4" />
              {snifferLoading ? 'Đang dừng...' : 'Dừng'}
            </button>
          ) : (
            <button
              onClick={handleStartSniffer}
              disabled={snifferLoading || !selectedIface}
              className="flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 transition-colors"
            >
              <Radio className="w-4 h-4" />
              {snifferLoading ? 'Đang khởi động...' : 'Bắt đầu bắt gói tin'}
            </button>
          )}

          {/* Error message */}
          {snifferError && (
            <span className="text-xs text-red-400 bg-red-950/40 border border-red-700/30 rounded-lg px-3 py-1.5 max-w-sm">
              {snifferError}
            </span>
          )}
        </div>
      </div>

      {/* KPI Cards */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { title: 'Active Flows',    value: stats.flows?.active_flows?.toLocaleString() || 0,  color: '#3b82f6', icon: Network },
            { title: 'Total Created',   value: stats.flows?.total_flows_created?.toLocaleString() || 0, color: '#8b5cf6', icon: Activity },
            { title: 'Pkts Captured',   value: (stats.pipeline?.sniffer_stats?.packets_captured || 0).toLocaleString(), color: '#22c55e', icon: Zap },
            { title: 'Pkts/sec',        value: (stats.pipeline?.sniffer_stats?.packets_per_second || 0).toFixed(1), color: '#f59e0b', icon: Activity },
          ].map(({ title, value, color, icon: Icon }) => (
            <div key={title} className="bg-slate-900/60 border border-slate-800/60 rounded-xl p-4 flex items-center gap-3">
              <div className="p-2.5 rounded-xl shrink-0" style={{ background: color + '15' }}>
                <Icon className="w-5 h-5" style={{ color }} />
              </div>
              <div>
                <p className="text-xs text-slate-500">{title}</p>
                <p className="text-xl font-bold" style={{ color }}>{value}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Live Traffic Trend */}
        <div className="lg:col-span-2 bg-slate-900/60 border border-slate-800/60 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4 text-green-400" /> Active Flows (realtime)
          </h3>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={trafficHistory}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#64748b' }} />
              <YAxis tick={{ fontSize: 10, fill: '#64748b' }} />
              <Tooltip contentStyle={CHART_STYLE} itemStyle={CHART_ITEM_STYLE} labelStyle={CHART_LABEL_STYLE} wrapperStyle={CHART_WRAPPER_STYLE} />
              <Line type="monotone" dataKey="flows" stroke="#22c55e" strokeWidth={2} dot={false} name="Flows" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Protocol Pie */}
        <div className="bg-slate-900/60 border border-slate-800/60 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Giao thức</h3>
          {protocolData.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={140}>
                <PieChart>
                  <Pie data={protocolData} dataKey="count" nameKey="name" cx="50%" cy="50%"
                    outerRadius={60} innerRadius={30}>
                    {protocolData.map((e, i) => (
                      <Cell key={i} fill={PROTOCOL_COLORS[e.name] || '#64748b'} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={CHART_STYLE} itemStyle={CHART_ITEM_STYLE} labelStyle={CHART_LABEL_STYLE} wrapperStyle={CHART_WRAPPER_STYLE} formatter={(v, n) => [v, String(n).toUpperCase()]} />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-1 mt-1">
                {protocolData.map(p => {
                  const total = protocolData.reduce((s, x) => s + x.count, 0)
                  return (
                    <div key={p.name} className="flex items-center justify-between text-xs">
                      <span className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full" style={{ background: PROTOCOL_COLORS[p.name] || '#64748b' }} />
                        <span className="text-slate-400 uppercase">{p.name}</span>
                      </span>
                      <span className="text-slate-300 font-medium">
                        {total > 0 ? Math.round(p.count / total * 100) : 0}%
                      </span>
                    </div>
                  )
                })}
              </div>
            </>
          ) : (
            <div className="h-[180px] flex items-center justify-center text-slate-600 text-sm">
              Không có dữ liệu
            </div>
          )}
        </div>
      </div>

      {/* Top Talkers + Top Ports */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Top Talkers */}
        {topTalkers.length > 0 && (
          <div className="bg-slate-900/60 border border-slate-800/60 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-slate-300 mb-4">Top Talkers (packet count)</h3>
            <div className="space-y-2">
              {topTalkers.map((t, i) => (
                <div key={i} className="flex items-center gap-3">
                  <span className="text-xs text-slate-600 w-4">{i + 1}</span>
                  <span className="font-mono text-xs text-blue-400 w-32 shrink-0">{t.src_ip}</span>
                  <div className="flex-1 bg-slate-800 rounded-full h-1.5">
                    <div className="bg-blue-500 h-1.5 rounded-full"
                      style={{ width: `${Math.min(100, t.packet_count / (topTalkers[0]?.packet_count || 1) * 100)}%` }} />
                  </div>
                  <span className="text-xs text-slate-400 w-16 text-right">
                    {t.packet_count?.toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Top Destination Ports */}
        {topPorts.length > 0 && (
          <div className="bg-slate-900/60 border border-slate-800/60 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-slate-300 mb-4">Top Destination Ports</h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={topPorts} margin={{ top: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="port" tick={{ fontSize: 10, fill: '#64748b' }} />
                <YAxis tick={{ fontSize: 10, fill: '#64748b' }} />
                <Tooltip contentStyle={CHART_STYLE} itemStyle={CHART_ITEM_STYLE} labelStyle={CHART_LABEL_STYLE} wrapperStyle={CHART_WRAPPER_STYLE} />
                <Bar dataKey="count" fill="#8b5cf6" radius={[3, 3, 0, 0]} name="Flows" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Packet Inspection Table */}
      <div className="bg-slate-900/60 border border-slate-800/60 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-800/60 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-300">
            Packet Inspection ({filteredFlows.length} flows)
          </h3>
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-slate-500" />
            <select value={filterProto} onChange={e => { setFilterProto(e.target.value); _filterProtoCache = e.target.value }}
              className="px-2 py-1 text-xs bg-slate-800 border border-slate-700 rounded-lg text-slate-300">
              <option value="">All Protocols</option>
              <option value="tcp">TCP</option>
              <option value="udp">UDP</option>
              <option value="icmp">ICMP</option>
            </select>
          </div>
        </div>

        {loading ? (
          <div className="p-8 text-center text-slate-500">
            <RefreshCw className="w-6 h-6 mx-auto mb-2 animate-spin opacity-40" />
            <p className="text-sm">Đang tải...</p>
          </div>
        ) : filteredFlows.length === 0 ? (
          <div className="p-8 text-center text-slate-600">
            <Network className="w-8 h-8 mx-auto mb-2 opacity-30" />
            <p className="text-sm">Không có flows{stats?.pipeline?.is_running ? '' : ' — Pipeline chưa chạy'}</p>
          </div>
        ) : (
          <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-slate-900 border-b border-slate-800 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2 text-left">Source</th>
                  <th className="px-4 py-2 text-left">Destination</th>
                  <th className="px-4 py-2 text-left">Proto</th>
                  <th className="px-4 py-2 text-right">Pkts</th>
                  <th className="px-4 py-2 text-right">Bytes</th>
                  <th className="px-4 py-2 text-right">Duration</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/40">
                {filteredFlows.slice(0, 100).map((flow, i) => (
                  <tr key={i} className="hover:bg-slate-800/30 transition-colors">
                    <td className="px-4 py-2 font-mono text-xs text-slate-300">
                      {flow.src_ip}:{flow.src_port || '—'}
                    </td>
                    <td className="px-4 py-2 font-mono text-xs text-slate-300">
                      {flow.dst_ip}:{flow.dst_port || '—'}
                    </td>
                    <td className="px-4 py-2 text-xs font-semibold uppercase"
                      style={{ color: PROTOCOL_COLORS[String(flow.protocol ?? '').toLowerCase()] || '#64748b' }}>
                      {flow.protocol}
                    </td>
                    <td className="px-4 py-2 text-right text-xs text-slate-400">{flow.packet_count}</td>
                    <td className="px-4 py-2 text-right text-xs text-slate-400">
                      {(flow.byte_count / 1024).toFixed(1)} KB
                    </td>
                    <td className="px-4 py-2 text-right text-xs text-slate-400">
                      {flow.flow_duration?.toFixed(2)}s
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
