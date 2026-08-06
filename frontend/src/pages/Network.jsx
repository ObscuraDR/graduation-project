import { useEffect, useState } from 'react'
import { Network as NetworkIcon, Activity, Filter } from 'lucide-react'
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer
} from 'recharts'
import { fetchActiveFlows, fetchTrafficStats, fetchTopTalkers } from '../lib/api'

const PROTOCOL_COLORS = {
  tcp: '#3b82f6',
  udp: '#22c55e',
  icmp: '#f59e0b',
  unknown: '#94a3b8',
}

const CHART_TOOLTIP_STYLE = {
  background: '#0f172a',
  border: '1px solid #334155',
  borderRadius: '8px',
  color: '#e2e8f0',
}

// Module-level cache
let _networkCache = null

export default function Network() {
  const [flows, setFlows] = useState(_networkCache?.flows || [])
  const [stats, setStats] = useState(_networkCache?.stats || null)
  const [topTalkers, setTopTalkers] = useState(_networkCache?.topTalkers || [])
  const [loading, setLoading] = useState(!_networkCache)
  const [filterProto, setFilterProto] = useState('')

  const loadData = async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const [flowsData, statsData, talkersData] = await Promise.all([
        fetchActiveFlows(200),
        fetchTrafficStats(),
        fetchTopTalkers(10),
      ])
      setFlows(flowsData)
      setStats(statsData)
      setTopTalkers(talkersData)
      _networkCache = { flows: flowsData, stats: statsData, topTalkers: talkersData }
    } catch (err) {
      console.error('Failed to load network data:', err)
    }
    if (!silent) setLoading(false)
  }

  useEffect(() => {
    loadData()
    const interval = setInterval(() => loadData(true), 10000)
    return () => clearInterval(interval)
  }, [])

  // Aggregate protocol distribution
  const protocolStats = flows.reduce((acc, flow) => {
    const proto = String(flow.protocol ?? 'unknown').toLowerCase()
    if (!acc[proto]) acc[proto] = { name: proto, count: 0, packets: 0, bytes: 0 }
    acc[proto].count += 1
    acc[proto].packets += flow.packet_count || 0
    acc[proto].bytes += flow.byte_count || 0
    return acc
  }, {})
  const protocolData = Object.values(protocolStats)

  // Aggregate top destination ports
  const portStats = flows.reduce((acc, flow) => {
    if (!flow.dst_port) return acc
    const key = `${flow.dst_port}`
    if (!acc[key]) acc[key] = { port: flow.dst_port, count: 0 }
    acc[key].count += 1
    return acc
  }, {})
  const topPorts = Object.values(portStats)
    .sort((a, b) => b.count - a.count)
    .slice(0, 10)

  // Filter flows by protocol
  const filteredFlows = filterProto
    ? flows.filter((f) => String(f.protocol ?? '').toLowerCase() === filterProto)
    : flows

  const thClass = 'text-left px-4 py-3 font-medium text-slate-400 text-xs uppercase tracking-wider'

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Network Analysis</h1>
          <p className="text-sm text-slate-500 mt-0.5">Protocol breakdown and packet inspection</p>
        </div>
        <button
          onClick={loadData}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm text-white transition-colors shadow-lg shadow-blue-500/20"
        >
          <Activity className="w-4 h-4" /> Refresh
        </button>
      </div>

      {/* Summary Cards */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            {
              title: 'Active Flows',
              value: (stats.flows?.active_flows || 0).toLocaleString(),
              subtitle: 'Currently tracked',
              icon: NetworkIcon,
              color: '#3b82f6',
              borderColor: 'border-blue-500/20',
              bgColor: 'bg-blue-500/10',
            },
            {
              title: 'Total Flows Created',
              value: (stats.flows?.total_flows_created || 0).toLocaleString(),
              subtitle: 'Since pipeline start',
              icon: Activity,
              color: '#8b5cf6',
              borderColor: 'border-violet-500/20',
              bgColor: 'bg-violet-500/10',
            },
            {
              title: 'Packets Captured',
              value: (stats.pipeline?.sniffer_stats?.packets_captured || 0).toLocaleString(),
              subtitle: 'Total intercepted',
              icon: Filter,
              color: '#22c55e',
              borderColor: 'border-emerald-500/20',
              bgColor: 'bg-emerald-500/10',
            },
            {
              title: 'Packets / sec',
              value: (stats.pipeline?.sniffer_stats?.packets_per_second || 0).toFixed(1),
              subtitle: 'Live throughput',
              icon: Activity,
              color: stats.pipeline?.sniffer_stats?.packets_per_second > 0 ? '#f59e0b' : '#64748b',
              borderColor: stats.pipeline?.sniffer_stats?.packets_per_second > 0 ? 'border-amber-500/20' : 'border-slate-700/40',
              bgColor: stats.pipeline?.sniffer_stats?.packets_per_second > 0 ? 'bg-amber-500/10' : 'bg-slate-800/40',
              live: stats.pipeline?.sniffer_stats?.packets_per_second > 0,
            },
          ].map(({ title, value, subtitle, icon: Icon, color, borderColor, bgColor, live }) => (
            <div key={title} className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 p-5 hover:border-slate-700/60 transition-all">
              <div className={`inline-flex p-2.5 rounded-xl border ${borderColor} ${bgColor} mb-3`}>
                <Icon className="w-5 h-5" style={{ color }} />
              </div>
              <div className="flex items-center gap-2 mb-1">
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">{title}</p>
                {live && (
                  <span className="flex h-2 w-2 relative">
                    <span className="animate-ping absolute h-2 w-2 rounded-full bg-amber-400 opacity-75" />
                    <span className="h-2 w-2 rounded-full bg-amber-500" />
                  </span>
                )}
              </div>
              <p className="text-2xl font-bold leading-tight" style={{ color }}>{value}</p>
              <p className="text-xs text-slate-600 mt-0.5">{subtitle}</p>
            </div>
          ))}
        </div>
      )}

      {/* Protocol Distribution & Top Ports */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Protocol Pie */}
        <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
            <NetworkIcon className="w-4 h-4 text-blue-400" /> Protocol Distribution
          </h3>
          {protocolData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  data={protocolData}
                  dataKey="count"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={90}
                  label={(entry) => `${(entry.name || 'unknown').toUpperCase()} (${entry.count})`}
                  labelLine={{ stroke: '#475569' }}
                >
                  {protocolData.map((entry, i) => (
                    <Cell key={i} fill={PROTOCOL_COLORS[entry.name] || '#94a3b8'} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v, n) => [`${v} flows`, String(n).toUpperCase()]}
                  contentStyle={CHART_TOOLTIP_STYLE}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[280px] flex items-center justify-center text-slate-600 text-sm">No traffic data</div>
          )}
        </div>

        {/* Top Destination Ports */}
        <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Top Destination Ports</h3>
          {topPorts.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={topPorts}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="port" tick={{ fontSize: 11, fill: '#64748b' }} />
                <YAxis tick={{ fontSize: 11, fill: '#64748b' }} />
                <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
                <Bar dataKey="count" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[280px] flex items-center justify-center text-slate-600 text-sm">No port data</div>
          )}
        </div>
      </div>

      {/* Top Talkers */}
      {topTalkers.length > 0 && (
        <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Top Talkers (by packet count)</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
            {topTalkers.map((talker, i) => (
              <div key={i} className="p-3 bg-slate-800/50 border border-slate-700/40 rounded-lg hover:border-slate-600/60 transition-colors">
                <div className="text-xs text-slate-600 mb-1">#{i + 1}</div>
                <div className="text-sm font-mono font-medium text-blue-400 mb-1 truncate">{talker.src_ip}</div>
                <div className="text-xs text-slate-500">
                  {talker.packet_count?.toLocaleString()} pkts · {talker.flow_count} flows
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Protocol Statistics Table */}
      <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-800/60">
          <h3 className="text-sm font-semibold text-slate-300">Protocol Statistics</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-800/80 border-b border-slate-700/60">
              <tr>
                <th className={thClass}>Protocol</th>
                <th className={`${thClass} text-right`}>Flows</th>
                <th className={`${thClass} text-right`}>Packets</th>
                <th className={`${thClass} text-right`}>Bytes</th>
                <th className={`${thClass} text-right`}>% of Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {protocolData.length > 0 ? protocolData.map((p) => {
                const total = protocolData.reduce((s, x) => s + x.count, 0)
                const pct = total > 0 ? (p.count / total * 100).toFixed(1) : 0
                return (
                  <tr key={p.name} className="hover:bg-slate-800/40 transition-colors">
                    <td className="px-4 py-2.5 uppercase font-semibold text-xs" style={{ color: PROTOCOL_COLORS[p.name] || '#94a3b8' }}>
                      {p.name}
                    </td>
                    <td className="px-4 py-2.5 text-right text-slate-300">{p.count}</td>
                    <td className="px-4 py-2.5 text-right text-slate-300">{p.packets.toLocaleString()}</td>
                    <td className="px-4 py-2.5 text-right text-slate-300">{(p.bytes / 1024).toFixed(1)} KB</td>
                    <td className="px-4 py-2.5 text-right text-slate-300">{pct}%</td>
                  </tr>
                )
              }) : (
                <tr><td colSpan="5" className="px-4 py-8 text-center text-slate-600">No data</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Packet Inspection Table */}
      <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-800/60 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-300">
            Packet Inspection ({filteredFlows.length} flows)
          </h3>
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-slate-500" />
            <select
              value={filterProto}
              onChange={(e) => setFilterProto(e.target.value)}
              className="px-3 py-1.5 border border-slate-700 rounded-lg text-sm bg-slate-800 text-slate-300 focus:outline-none focus:border-blue-500 transition-colors"
            >
              <option value="">All Protocols</option>
              <option value="tcp">TCP</option>
              <option value="udp">UDP</option>
              <option value="icmp">ICMP</option>
            </select>
          </div>
        </div>
        {loading ? (
          <div className="p-8 text-center text-slate-600">Loading...</div>
        ) : filteredFlows.length === 0 ? (
          <div className="p-8 text-center text-slate-600">No flows captured</div>
        ) : (
          <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-800/80 border-b border-slate-700/60 sticky top-0">
                <tr>
                  <th className={thClass}>Source</th>
                  <th className={thClass}>Destination</th>
                  <th className={thClass}>Proto</th>
                  <th className={`${thClass} text-right`}>Pkts</th>
                  <th className={`${thClass} text-right`}>Bytes</th>
                  <th className={`${thClass} text-right`}>Duration</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredFlows.slice(0, 100).map((flow, i) => (
                  <tr key={i} className="hover:bg-slate-800/40 transition-colors">
                    <td className="px-4 py-2 font-mono text-xs text-slate-300">
                      {flow.src_ip}:{flow.src_port || '-'}
                    </td>
                    <td className="px-4 py-2 font-mono text-xs text-slate-300">
                      {flow.dst_ip}:{flow.dst_port || '-'}
                    </td>
                    <td
                      className="px-4 py-2 uppercase font-semibold text-xs"
                      style={{ color: PROTOCOL_COLORS[String(flow.protocol ?? '').toLowerCase()] || '#94a3b8' }}
                    >
                      {flow.protocol}
                    </td>
                    <td className="px-4 py-2 text-right text-slate-400">{flow.packet_count}</td>
                    <td className="px-4 py-2 text-right text-slate-400">{(flow.byte_count / 1024).toFixed(1)} KB</td>
                    <td className="px-4 py-2 text-right text-slate-400">{flow.flow_duration?.toFixed(2)}s</td>
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
