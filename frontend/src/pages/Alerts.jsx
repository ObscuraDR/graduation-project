import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle, Trash2, RefreshCw, Eye, Download, Activity, Zap } from 'lucide-react'
import SeverityBadge from '../components/SeverityBadge'
import AlertDetailModal from '../components/AlertDetailModal'
import { fetchAlerts, resolveAlert, deleteAlert } from '../lib/api'
import { hasRole } from '../lib/auth'
import { formatDatetime } from '../lib/datetime'
import { connectWebSocket, onWebSocketMessage } from '../lib/websocket'

// Module-level cache
let _alertsCache = []

const SEVERITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3 }
const SEVERITY_COLORS = {
  critical: 'border-l-red-500 bg-red-50/40',
  high: 'border-l-orange-400 bg-orange-50/40',
  medium: 'border-l-blue-400 bg-blue-50/40',
  low: 'border-l-green-400 bg-green-50/40',
}

export default function Alerts() {
  const [alerts, setAlerts] = useState(_alertsCache)
  const [loading, setLoading] = useState(_alertsCache.length === 0)
  const [filter, setFilter] = useState({ severity: '', status: '', attackType: '' })
  const [selectedAlert, setSelectedAlert] = useState(null)
  const [liveAlerts, setLiveAlerts] = useState([])
  const [liveCount, setLiveCount] = useState(0)

  const loadAlerts = async () => {
    setLoading(true)
    try {
      const data = await fetchAlerts({ limit: 100, ...filter })
      setAlerts(data)
      _alertsCache = data
    } catch (err) {
      console.error('Failed to fetch alerts:', err)
    }
    setLoading(false)
  }

  useEffect(() => {
    loadAlerts()
  }, [filter])

  // WebSocket cho Live Feed
  useEffect(() => {
    connectWebSocket()
    const unsub = onWebSocketMessage((msg) => {
      if (msg.type === 'alert') {
        setLiveAlerts((prev) => [msg.data, ...prev].slice(0, 20))
        setLiveCount((n) => n + 1)
      }
    })
    return () => unsub()
  }, [])

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
    if (!confirm('Xóa cảnh báo này vĩnh viễn?')) return
    try {
      await deleteAlert(alertId)
      loadAlerts()
    } catch (err) {
      console.error('Failed to delete alert:', err)
    }
  }

  const exportCSV = () => {
    if (alerts.length === 0) return
    const headers = ['Alert ID', 'Attack Type', 'Severity', 'Confidence', 'Source IP', 'Dest IP', 'Status', 'Timestamp']
    const rows = alerts.map((a) => [
      a.alert_id, a.attack_type, a.severity,
      ((a.confidence ?? 0) * 100).toFixed(1) + '%',
      a.source_ip || '', a.dest_ip || '',
      a.status, a.timestamp || '',
    ])
    const csv = [headers.join(','), ...rows.map((r) => r.map((c) => `"${c}"`).join(','))].join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ids-alerts-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="p-6 h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Cảnh báo</h1>
          <p className="text-sm text-gray-400">{alerts.length} bản ghi trong database</p>
        </div>
        <div className="flex gap-2">
          <button onClick={exportCSV} disabled={alerts.length === 0}
            className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:bg-gray-50 disabled:opacity-40">
            <Download className="w-4 h-4" /> Export CSV
          </button>
          <button onClick={loadAlerts}
            className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:bg-gray-50">
            <RefreshCw className="w-4 h-4" /> Làm mới
          </button>
        </div>
      </div>

      {/* Split layout */}
      <div className="flex gap-4 h-[calc(100vh-180px)]">

        {/* ── TRÁI: Bảng alerts (2/3) ── */}
        <div className="flex-[2] flex flex-col min-w-0">
          {/* Filters */}
          <div className="flex gap-2 mb-3 flex-wrap">
            <select value={filter.attackType}
              onChange={(e) => setFilter((f) => ({ ...f, attackType: e.target.value }))}
              className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm bg-white">
              <option value="">Tất cả loại tấn công</option>
              <option value="DDoS">DDoS</option>
              <option value="PortScan">PortScan</option>
              <option value="BruteForce">BruteForce</option>
              <option value="Botnet">Botnet</option>
              <option value="Abnormal">Abnormal</option>
            </select>
            <select value={filter.severity}
              onChange={(e) => setFilter((f) => ({ ...f, severity: e.target.value }))}
              className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm bg-white">
              <option value="">Tất cả mức độ</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
            <select value={filter.status}
              onChange={(e) => setFilter((f) => ({ ...f, status: e.target.value }))}
              className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm bg-white">
              <option value="">Tất cả trạng thái</option>
              <option value="active">Đang hoạt động</option>
              <option value="resolved">Đã xử lý</option>
            </select>
          </div>

          {/* Table */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden flex-1 flex flex-col">
            {loading ? (
              <div className="flex-1 flex items-center justify-center text-gray-400">
                <div className="text-center">
                  <RefreshCw className="w-8 h-8 mx-auto mb-2 animate-spin opacity-40" />
                  <p className="text-sm">Đang tải...</p>
                </div>
              </div>
            ) : alerts.length === 0 ? (
              <div className="flex-1 flex items-center justify-center text-gray-400">
                <div className="text-center">
                  <AlertTriangle className="w-12 h-12 mx-auto mb-3 text-gray-200" />
                  <p className="text-sm">Không có cảnh báo nào</p>
                </div>
              </div>
            ) : (
              <div className="overflow-auto flex-1">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-100 sticky top-0">
                    <tr>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Loại tấn công</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Source IP</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Mức độ</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Confidence</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Thời gian</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Trạng thái</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Thao tác</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {alerts.map((alert) => (
                      <tr key={alert.alert_id}
                        className="hover:bg-gray-50 cursor-pointer transition-colors"
                        onClick={() => setSelectedAlert(alert)}>
                        <td className="px-4 py-3 font-medium text-gray-800">{alert.attack_type}</td>
                        <td className="px-4 py-3 text-gray-500 font-mono text-xs">{alert.source_ip}</td>
                        <td className="px-4 py-3"><SeverityBadge severity={alert.severity} /></td>
                        <td className="px-4 py-3 text-gray-500">{((alert.confidence ?? 0) * 100).toFixed(1)}%</td>
                        <td className="px-4 py-3 text-gray-400 text-xs">{formatDatetime(alert.timestamp)}</td>
                        <td className="px-4 py-3">
                          <span className={`text-xs font-medium ${alert.is_resolved ? 'text-green-600' : 'text-orange-500'}`}>
                            {alert.is_resolved ? '✓ Đã xử lý' : '● Đang hoạt động'}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex gap-1">
                            <button onClick={(e) => { e.stopPropagation(); setSelectedAlert(alert) }}
                              className="p-1.5 text-blue-400 hover:bg-blue-50 rounded" title="Xem chi tiết">
                              <Eye className="w-4 h-4" />
                            </button>
                            {!alert.is_resolved && hasRole(['admin', 'security_analyst']) && (
                              <button onClick={(e) => handleResolve(alert.alert_id, e)}
                                className="p-1.5 text-green-500 hover:bg-green-50 rounded" title="Đánh dấu đã xử lý">
                                <CheckCircle className="w-4 h-4" />
                              </button>
                            )}
                            {hasRole(['admin']) && (
                              <button onClick={(e) => handleDelete(alert.alert_id, e)}
                                className="p-1.5 text-red-400 hover:bg-red-50 rounded" title="Xóa">
                                <Trash2 className="w-4 h-4" />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* ── PHẢI: Live Alert Feed (1/3) ── */}
        <div className="flex-1 min-w-[260px] max-w-[340px] flex flex-col bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          {/* Header live feed */}
          <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between bg-gray-50">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              <span className="text-sm font-semibold text-gray-700">Live Alert Feed</span>
            </div>
            {liveCount > 0 && (
              <span className="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded-full font-medium">
                +{liveCount} mới
              </span>
            )}
          </div>

          {/* Live list */}
          <div className="flex-1 overflow-y-auto divide-y divide-gray-50">
            {liveAlerts.length > 0 ? (
              liveAlerts.map((alert, i) => (
                <div key={i}
                  className={`px-4 py-3 border-l-4 cursor-pointer hover:brightness-95 transition-all ${SEVERITY_COLORS[alert.severity] || 'border-l-gray-300'}`}
                  onClick={() => setSelectedAlert({
                    alert_id: alert.alert_id,
                    attack_type: alert.attack_type,
                    source_ip: alert.src_ip,
                    dest_ip: alert.dst_ip,
                    source_port: alert.src_port,
                    dest_port: alert.dst_port,
                    protocol: alert.protocol,
                    severity: alert.severity,
                    confidence: alert.confidence,
                    timestamp: alert.timestamp,
                    model_name: alert.model_name,
                    all_probabilities: alert.all_probabilities,
                    is_resolved: false,
                  })}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-gray-800 truncate">{alert.attack_type}</p>
                      <p className="text-xs text-gray-500 font-mono truncate">{alert.src_ip}</p>
                      <p className="text-xs text-gray-300 mt-0.5">{formatDatetime(alert.timestamp)}</p>
                    </div>
                    <SeverityBadge severity={alert.severity} />
                  </div>
                  {alert.confidence && (
                    <div className="mt-1.5">
                      <div className="w-full bg-gray-100 rounded-full h-1">
                        <div
                          className="h-1 rounded-full bg-red-400 transition-all"
                          style={{ width: `${Math.round(alert.confidence * 100)}%` }}
                        />
                      </div>
                      <p className="text-xs text-gray-400 mt-0.5">{Math.round(alert.confidence * 100)}% confidence</p>
                    </div>
                  )}
                </div>
              ))
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center p-6 text-center h-full">
                <Activity className="w-10 h-10 text-gray-200 mb-3" />
                <p className="text-sm text-gray-400">Chưa có alert real-time</p>
                <p className="text-xs text-gray-300 mt-1">
                  Chạy demo để xem luồng tấn công
                </p>
                <div className="mt-4 px-3 py-2 bg-gray-50 rounded-lg text-xs text-gray-500 font-mono">
                  .\demo.ps1 -Action demo-start
                </div>
              </div>
            )}
          </div>

          {/* Footer stats */}
          {liveAlerts.length > 0 && (
            <div className="px-4 py-2 border-t border-gray-100 bg-gray-50 flex justify-between text-xs text-gray-400">
              <span>{liveAlerts.length} alerts</span>
              <button
                onClick={() => { setLiveAlerts([]); setLiveCount(0) }}
                className="text-gray-400 hover:text-red-400 transition-colors"
              >
                Xóa feed
              </button>
            </div>
          )}
        </div>

      </div>

      {/* Detail Modal */}
      {selectedAlert && (
        <AlertDetailModal alert={selectedAlert} onClose={() => setSelectedAlert(null)} />
      )}
    </div>
  )
}
