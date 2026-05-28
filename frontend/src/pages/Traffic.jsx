import { useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { fetchActiveFlows, fetchTopTalkers, fetchTrafficStats } from '../lib/api'

export default function Traffic() {
  const [flows, setFlows] = useState([])
  const [topTalkers, setTopTalkers] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  const loadData = async () => {
    setLoading(true)
    try {
      const [flowsData, talkersData, statsData] = await Promise.all([
        fetchActiveFlows(50),
        fetchTopTalkers(10),
        fetchTrafficStats(),
      ])
      setFlows(flowsData)
      setTopTalkers(talkersData)
      setStats(statsData)
    } catch (err) {
      console.error('Failed to load traffic data:', err)
    }
    setLoading(false)
  }

  useEffect(() => { loadData() }, [])

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Traffic Analysis</h1>
          <p className="text-sm text-gray-500">Active flows and network statistics</p>
        </div>
        <button onClick={loadData} className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:bg-gray-50">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {/* Stats Summary */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
            <p className="text-sm text-gray-500">Active Flows</p>
            <p className="text-2xl font-bold text-gray-900">{stats.flows?.active_flows || 0}</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
            <p className="text-sm text-gray-500">Total Created</p>
            <p className="text-2xl font-bold text-gray-900">{stats.flows?.total_flows_created || 0}</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
            <p className="text-sm text-gray-500">Pipeline Packets</p>
            <p className="text-2xl font-bold text-gray-900">{stats.pipeline?.processed_packets || 0}</p>
          </div>
        </div>
      )}

      {/* Top Talkers Chart */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">Top Talkers (by packet count)</h3>
        {topTalkers.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={topTalkers} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="src_ip" tick={{ fontSize: 11 }} width={120} />
              <Tooltip />
              <Bar dataKey="packet_count" fill="#3b82f6" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-sm text-gray-400 text-center py-8">No traffic data available</p>
        )}
      </div>

      {/* Active Flows Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100">
          <h3 className="text-sm font-semibold text-gray-700">Active Flows ({flows.length})</h3>
        </div>
        {loading ? (
          <div className="p-8 text-center text-gray-400">Loading...</div>
        ) : flows.length === 0 ? (
          <div className="p-8 text-center text-gray-400">No active flows. Start the pipeline to see traffic.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Source</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Destination</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Protocol</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Packets</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Bytes</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Duration</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {flows.map((flow, i) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs">{flow.src_ip}:{flow.src_port}</td>
                    <td className="px-4 py-3 font-mono text-xs">{flow.dst_ip}:{flow.dst_port}</td>
                    <td className="px-4 py-3 uppercase text-xs font-medium">{flow.protocol}</td>
                    <td className="px-4 py-3">{flow.packet_count}</td>
                    <td className="px-4 py-3">{(flow.byte_count / 1024).toFixed(1)} KB</td>
                    <td className="px-4 py-3">{flow.flow_duration?.toFixed(1)}s</td>
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
