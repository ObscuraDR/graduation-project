import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle, Trash2, RefreshCw, Eye, Download } from 'lucide-react'
import SeverityBadge from '../components/SeverityBadge'
import AlertDetailModal from '../components/AlertDetailModal'
import { fetchAlerts, resolveAlert, deleteAlert } from '../lib/api'

export default function Alerts() {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState({ severity: '', status: '' })
  const [selectedAlert, setSelectedAlert] = useState(null)

  const loadAlerts = async () => {
    setLoading(true)
    try {
      const data = await fetchAlerts({ limit: 100, ...filter })
      setAlerts(data)
    } catch (err) {
      console.error('Failed to fetch alerts:', err)
    }
    setLoading(false)
  }

  useEffect(() => { loadAlerts() }, [filter])

  const handleResolve = async (alertId, e) => {
    e?.stopPropagation()
    try {
      await resolveAlert(alertId, 'Resolved from dashboard')
      loadAlerts()
    } catch (err) {
      console.error('Failed to resolve alert:', err)
    }
  }

  const handleDelete = async (alertId, e) => {
    e?.stopPropagation()
    if (!confirm('Delete this alert permanently?')) return
    try {
      await deleteAlert(alertId)
      loadAlerts()
    } catch (err) {
      console.error('Failed to delete alert:', err)
    }
  }

  const exportCSV = () => {
    if (alerts.length === 0) return
    const headers = ['Alert ID', 'Attack Type', 'Severity', 'Confidence', 'Source IP', 'Dest IP', 'Source Port', 'Dest Port', 'Status', 'Timestamp', 'Resolved At', 'Notes']
    const rows = alerts.map((a) => [
      a.alert_id,
      a.attack_type,
      a.severity,
      ((a.confidence ?? 0) * 100).toFixed(1) + '%',
      a.source_ip || '',
      a.dest_ip || '',
      a.source_port || '',
      a.dest_port || '',
      a.status,
      a.timestamp || '',
      a.resolved_at || '',
      (a.notes || '').replace(/"/g, '""'),
    ])

    const csv = [
      headers.join(','),
      ...rows.map((r) => r.map((c) => `"${c}"`).join(',')),
    ].join('\n')

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ids-alerts-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Alerts</h1>
          <p className="text-sm text-gray-500">{alerts.length} alerts found</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={exportCSV}
            disabled={alerts.length === 0}
            className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:bg-gray-50 disabled:opacity-50"
          >
            <Download className="w-4 h-4" /> Export CSV
          </button>
          <button
            onClick={loadAlerts}
            className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:bg-gray-50"
          >
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <select
          value={filter.severity}
          onChange={(e) => setFilter((f) => ({ ...f, severity: e.target.value }))}
          className="px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white"
        >
          <option value="">All Severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <select
          value={filter.status}
          onChange={(e) => setFilter((f) => ({ ...f, status: e.target.value }))}
          className="px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white"
        >
          <option value="">All Status</option>
          <option value="active">Active</option>
          <option value="resolved">Resolved</option>
        </select>
      </div>

      {/* Alert Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-400">Loading...</div>
        ) : alerts.length === 0 ? (
          <div className="p-8 text-center text-gray-400">
            <AlertTriangle className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            <p>No alerts found</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Attack Type</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Source IP</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Dest IP</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Severity</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Confidence</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Time</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {alerts.map((alert) => (
                <tr
                  key={alert.alert_id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => setSelectedAlert(alert)}
                >
                  <td className="px-4 py-3 font-medium text-gray-800">{alert.attack_type}</td>
                  <td className="px-4 py-3 text-gray-600 font-mono text-xs">{alert.source_ip}</td>
                  <td className="px-4 py-3 text-gray-600 font-mono text-xs">{alert.dest_ip}</td>
                  <td className="px-4 py-3"><SeverityBadge severity={alert.severity} /></td>
                  <td className="px-4 py-3 text-gray-600">{((alert.confidence ?? 0) * 100).toFixed(1)}%</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{alert.timestamp?.slice(0, 19).replace('T', ' ')}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium ${alert.is_resolved ? 'text-green-600' : 'text-orange-600'}`}>
                      {alert.is_resolved ? 'Resolved' : 'Active'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1">
                      <button
                        onClick={(e) => { e.stopPropagation(); setSelectedAlert(alert) }}
                        className="p-1.5 text-blue-500 hover:bg-blue-50 rounded"
                        title="View details"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                      {!alert.is_resolved && (
                        <button
                          onClick={(e) => handleResolve(alert.alert_id, e)}
                          className="p-1.5 text-green-600 hover:bg-green-50 rounded"
                          title="Resolve"
                        >
                          <CheckCircle className="w-4 h-4" />
                        </button>
                      )}
                      <button
                        onClick={(e) => handleDelete(alert.alert_id, e)}
                        className="p-1.5 text-red-500 hover:bg-red-50 rounded"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Detail Modal */}
      {selectedAlert && (
        <AlertDetailModal alert={selectedAlert} onClose={() => setSelectedAlert(null)} />
      )}
    </div>
  )
}
