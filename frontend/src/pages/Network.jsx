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

// Module-level cache
let _networkCache = null

export default function Network() {
  const [flows, setFlows] = useState(_networkCache?.flows || [])
  const [stats, setStats] = useState(_networkCache?.stats || null)
  const [topTalkers, setTopTalkers] = useState(_networkCache?.topTalkers || [])
  const [loading, setLoading] = useState(!_networkCache)
  const [filterProto, setFilterProto] = useState('')

  const loadData = async () => {
    setLoading(true)
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
    setLoading(false)
  }

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 10000)
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

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Network Analysis</h1>
          <p className="text-sm text-gray-500">Protocol breakdown and packet inspection</p>
        </div>
        <button
          onClick={loadData}
          className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 rounded-lg text-sm text-white transition-colors"
        >
          <Activity className="w-4 h-4" /> Refresh
        </button>
      </div>

      {/* Summary Cards */}
      {stats && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 divide-y md:divide-y-0 md:divide-x md:flex">
          {[
            {
              title: 'Active Flows',
              value: (stats.flows?.active_flows || 0).toLocaleString(),
              subtitle: 'Currently tracked',
              icon: NetworkIcon,
              color: '#3b82f6',
              bg: 'bg-blue-50',
            },
            {
              title: 'Total Flows Created',
              value: (stats.flows?.total_flows_created || 0).toLocaleString(),
              subtitle: 'Since pipeline start',
              icon: Activity,
              color: '#8b5cf6',
              bg: 'bg-purple-50',
            },
            {
              title: 'Packets Captured',
              value: (stats.pipeline?.sniffer_stats?.packets_captured || 0).toLocaleString(),
              subtitle: 'Total intercepted',
              icon: Filter,
              color: '#22c55e',
              bg: 'bg-green-50',
            },
            {
              title: 'Packets / sec',
              value: (stats.pipeline?.sniffer_stats?.packets_per_second || 0).toFixed(1),
              subtitle: 'Live throughput',
              icon: Activity,
              color: stats.pipeline?.sniffer_stats?.packets_per_second > 0 ? '#f59e0b' : '#94a3b8',
              bg: stats.pipeline?.sniffer_stats?.packets_per_second > 0 ? 'bg-yellow-50' : 'bg-gray-50',
              live: stats.pipeline?.sniffer_stats?.packets_per_second > 0,
            },
          ].map(({ title, value, subtitle, icon: Icon, color, bg, live }) => (
            <div key={title} className="flex-1 flex items-center gap-4 px-6 py-5">
              <div className={`p-3 rounded-xl ${bg} shrink-0`}>
                <Icon className="w-5 h-5" style={{ color }} />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{title}</p>
                  {live && <span className="flex h-2 w-2"><span className="animate-ping absolute h-2 w-2 rounded-full bg-yellow-400 opacity-75" /><span className="h-2 w-2 rounded-full bg-yellow-500" /></span>}
                </div>
                <p className="text-2xl font-bold leading-tight" style={{ color }}>{value}</p>
                <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Protocol Distribution & Top Ports */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Protocol Pie */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
            <NetworkIcon className="w-4 h-4" /> Protocol Distribution
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
                >
                  {protocolData.map((entry, i) => (
                    <Cell key={i} fill={PROTOCOL_COLORS[entry.name] || '#94a3b8'} />
                  ))}
                </Pie>
                <Tooltip formatter={(v, n) => [`${v} flows`, String(n).toUpperCase()]} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-gray-400 text-center py-8">No traffic data</p>
          )}
        </div>

        {/* Top Destination Ports */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Top Destination Ports</h3>
          {topPorts.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={topPorts}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="port" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-gray-400 text-center py-8">No port data</p>
          )}
        </div>
      </div>

      {/* Top Talkers */}
      {topTalkers.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Top Talkers (by packet count)</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
            {topTalkers.map((talker, i) => (
              <div key={i} className="p-3 bg-gray-50 rounded-lg">
                <div className="text-xs text-gray-500 mb-1">#{i + 1}</div>
                <div className="text-sm font-mono font-medium text-gray-900 mb-1">{talker.src_ip}</div>
                <div className="text-xs text-gray-600">
                  {talker.packet_count?.toLocaleString()} pkts • {talker.flow_count} flows
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Protocol Statistics Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">Protocol Statistics</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="text-left px-4 py-2 font-medium text-gray-600">Protocol</th>
                <th className="text-right px-4 py-2 font-medium text-gray-600">Flows</th>
                <th className="text-right px-4 py-2 font-medium text-gray-600">Packets</th>
                <th className="text-right px-4 py-2 font-medium text-gray-600">Bytes</th>
                <th className="text-right px-4 py-2 font-medium text-gray-600">% of Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {protocolData.length > 0 ? protocolData.map((p) => {
                const total = protocolData.reduce((s, x) => s + x.count, 0)
                const pct = total > 0 ? (p.count / total * 100).toFixed(1) : 0
                return (
                  <tr key={p.name}>
                    <td className="px-4 py-2 uppercase font-medium" style={{ color: PROTOCOL_COLORS[p.name] }}>
                      {p.name}
                    </td>
                    <td className="px-4 py-2 text-right">{p.count}</td>
                    <td className="px-4 py-2 text-right">{p.packets.toLocaleString()}</td>
                    <td className="px-4 py-2 text-right">{(p.bytes / 1024).toFixed(1)} KB</td>
                    <td className="px-4 py-2 text-right">{pct}%</td>
                  </tr>
                )
              }) : (
                <tr><td colSpan="5" className="px-4 py-8 text-center text-gray-400">No data</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Packet Inspection Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-700">
            Packet Inspection ({filteredFlows.length} flows)
          </h3>
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-400" />
            <select
              value={filterProto}
              onChange={(e) => setFilterProto(e.target.value)}
              className="px-3 py-1.5 border border-blue-500 rounded-lg text-sm bg-blue-600 text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Protocols</option>
              <option value="tcp">TCP</option>
              <option value="udp">UDP</option>
              <option value="icmp">ICMP</option>
            </select>
          </div>
        </div>
        {loading ? (
          <div className="p-8 text-center text-gray-400">Loading...</div>
        ) : filteredFlows.length === 0 ? (
          <div className="p-8 text-center text-gray-400">No flows captured</div>
        ) : (
          <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  <th className="text-left px-4 py-2 font-medium text-gray-600">Source</th>
                  <th className="text-left px-4 py-2 font-medium text-gray-600">Destination</th>
                  <th className="text-left px-4 py-2 font-medium text-gray-600">Proto</th>
                  <th className="text-right px-4 py-2 font-medium text-gray-600">Pkts</th>
                  <th className="text-right px-4 py-2 font-medium text-gray-600">Bytes</th>
                  <th className="text-right px-4 py-2 font-medium text-gray-600">Duration</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {filteredFlows.slice(0, 100).map((flow, i) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-4 py-2 font-mono text-xs">
                      {flow.src_ip}:{flow.src_port || '-'}
                    </td>
                    <td className="px-4 py-2 font-mono text-xs">
                      {flow.dst_ip}:{flow.dst_port || '-'}
                    </td>
                    <td
                      className="px-4 py-2 uppercase font-semibold text-xs"
                      style={{ color: PROTOCOL_COLORS[String(flow.protocol ?? '').toLowerCase()] || '#94a3b8' }}
                    >
                      {flow.protocol}
                    </td>
                    <td className="px-4 py-2 text-right">{flow.packet_count}</td>
                    <td className="px-4 py-2 text-right">{(flow.byte_count / 1024).toFixed(1)} KB</td>
                    <td className="px-4 py-2 text-right">{flow.flow_duration?.toFixed(2)}s</td>
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
