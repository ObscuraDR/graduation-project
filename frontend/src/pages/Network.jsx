import { useEffect, useState } from 'react'
import { Network as NetworkIcon, Activity, Filter } from 'lucide-react'
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer
} from 'recharts'
import { fetchActiveFlows, fetchTrafficStats } from '../lib/api'

const PROTOCOL_COLORS = {
  tcp: '#3b82f6',
  udp: '#22c55e',
  icmp: '#f59e0b',
  unknown: '#94a3b8',
}

export default function Network() {
  const [flows, setFlows] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filterProto, setFilterProto] = useState('')

  const loadData = async () => {
    setLoading(true)
    try {
      const [flowsData, statsData] = await Promise.all([
        fetchActiveFlows(200),
        fetchTrafficStats(),
      ])
      setFlows(flowsData)
      setStats(statsData)
    } catch (err) {
      console.error('Failed to load network data:', err)
    }
    setLoading(false)
  }

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 10000) // refresh mỗi 10s
    return () => clearInterval(interval)
  }, [])

  // Aggregate protocol distribution
  const protocolStats = flows.reduce((acc, flow) => {
    const proto = flow.protocol?.toLowerCase() || 'unknown'
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
    ? flows.filter((f) => f.protocol?.toLowerCase() === filterProto)
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
          className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:bg-gray-50"
        >
          <Activity className="w-4 h-4" /> Refresh
        </button>
      </div>

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
                  label={(entry) => `${entry.name.toUpperCase()} (${entry.count})`}
                >
                  {protocolData.map((entry, i) => (
                    <Cell key={i} fill={PROTOCOL_COLORS[entry.name] || '#94a3b8'} />
                  ))}
                </Pie>
                <Tooltip formatter={(v, n) => [`${v} flows`, n.toUpperCase()]} />
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
              className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm bg-white"
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
                      style={{ color: PROTOCOL_COLORS[flow.protocol?.toLowerCase()] || '#94a3b8' }}
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
