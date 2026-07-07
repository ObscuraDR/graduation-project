import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle, Trash2, RefreshCw, Eye, Download, Activity, Zap, Globe, Shield } from 'lucide-react'
import SeverityBadge from '../components/SeverityBadge'
import AlertDetailModal from '../components/AlertDetailModal'
import Pagination from '../components/Pagination'
import { fetchAlerts, resolveAlert, deleteAlert } from '../lib/api'
import { hasRole } from '../lib/auth'
import { formatDatetime } from '../lib/datetime'
import { connectWebSocket, onWebSocketMessage } from '../lib/websocket'

// Module-level cache
let _alertsCache = []

const SEVERITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3 }
const SEVERITY_LEFT_COLORS = {
  critical: 'border-l-red-500',
  high: 'border-l-orange-400',
  medium: 'border-l-blue-400',
  low: 'border-l-emerald-400',
}

export default function Alerts() {
  const [alerts, setAlerts] = useState(_alertsCache)
  const [loading, setLoading] = useState(_alertsCache.length === 0)
  const [filter, setFilter] = useState({ severity: '', status: '', attackType: '' })
  const [selectedAlert, setSelectedAlert] = useState(null)
  const [liveAlerts, setLiveAlerts] = useState([])
  const [liveCount, setLiveCount] = useState(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)
  const [totalPages, setTotalPages] = useState(1)

  const loadAlerts = async (page = currentPage) => {
    setLoading(true)
    try {
      const data = await fetchAlerts({ limit: pageSize, skip: (page - 1) * pageSize, ...filter })
      const items = data.items || data
      const total = data.total || items.length
      setAlerts(items)
      setTotalPages(Math.ceil(total / pageSize))
      _alertsCache = items
    } catch (err) {
      console.error('Failed to fetch alerts:', err)
    }
    setLoading(false)
  }

  // Khi filter thay đổi → reset về trang 1
  useEffect(() => {
    setCurrentPage(1)
    loadAlerts(1)
  }, [filter, pageSize])

  // Khi chuyển trang (không do filter)
  useEffect(() => {
    loadAlerts(currentPage)
  }, [currentPage])

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

  const selectClass = "px-3 py-1.5 border border-slate-700 rounded-lg text-sm bg-slate-800 text-slate-300 hover:border-slate-600 focus:outline-none focus:border-blue-500 transition-colors"

  return (
    <div className="h-full flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Cảnh báo</h1>
          <p className="text-sm text-slate-500 mt-0.5">{alerts.length} bản ghi trong database</p>
        </div>
        <div className="flex gap-2">
          <button onClick={exportCSV} disabled={alerts.length === 0}
            className="flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-sm text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
            <Download className="w-4 h-4" /> Export CSV
          </button>
          <button onClick={loadAlerts}
            className="flex items-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm text-white transition-colors">
            <RefreshCw className="w-4 h-4" /> Làm mới
          </button>
        </div>
      </div>

      {/* Split layout */}
      <div className="flex gap-4 flex-1 min-h-0" style={{ height: 'calc(100vh - 200px)' }}>

        {/* ── TRÁI: Bảng alerts (2/3) ── */}
        <div className="flex-[2] flex flex-col min-w-0">
          {/* Filters */}
          <div className="flex gap-2 mb-3 flex-wrap">
            <select value={filter.attackType}
              onChange={(e) => setFilter((f) => ({ ...f, attackType: e.target.value }))}
              className={selectClass}>
              <option value="">Tất cả loại tấn công</option>
              <option value="DDoS">DDoS</option>
              <option value="PortScan">PortScan</option>
              <option value="BruteForce">BruteForce</option>
              <option value="Botnet">Botnet</option>
              <option value="Abnormal">Abnormal</option>
            </select>
            <select value={filter.severity}
              onChange={(e) => setFilter((f) => ({ ...f, severity: e.target.value }))}
              className={selectClass}>
              <option value="">Tất cả mức độ</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
            <select value={filter.status}
              onChange={(e) => setFilter((f) => ({ ...f, status: e.target.value }))}
              className={selectClass}>
              <option value="">Tất cả trạng thái</option>
              <option value="active">Đang hoạt động</option>
              <option value="resolved">Đã xử lý</option>
            </select>
          </div>

          {/* Table */}
          <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 overflow-hidden flex-1 flex flex-col">
            {loading ? (
              <div className="flex-1 flex items-center justify-center text-slate-500">
                <div className="text-center">
                  <RefreshCw className="w-8 h-8 mx-auto mb-2 animate-spin opacity-40" />
                  <p className="text-sm">Đang tải...</p>
                </div>
              </div>
            ) : alerts.length === 0 ? (
              <div className="flex-1 flex items-center justify-center text-slate-600">
                <div className="text-center">
                  <AlertTriangle className="w-12 h-12 mx-auto mb-3 opacity-30" />
                  <p className="text-sm">Không có cảnh báo nào</p>
                </div>
              </div>
            ) : (
              <>
                <div className="overflow-auto flex-1">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-800/80 border-b border-slate-700/60 sticky top-0">
                      <tr>
                        <th className="text-left px-4 py-3 font-medium text-slate-400 text-xs uppercase tracking-wider">Loại tấn công</th>
                        <th className="text-left px-4 py-3 font-medium text-slate-400 text-xs uppercase tracking-wider">Source IP</th>
                        <th className="text-left px-4 py-3 font-medium text-slate-400 text-xs uppercase tracking-wider">Mức độ</th>
                        <th className="text-left px-4 py-3 font-medium text-slate-400 text-xs uppercase tracking-wider">Confidence</th>
                        <th className="text-left px-4 py-3 font-medium text-slate-400 text-xs uppercase tracking-wider">Thời gian</th>
                        <th className="text-left px-4 py-3 font-medium text-slate-400 text-xs uppercase tracking-wider">Trạng thái</th>
                        <th className="text-left px-4 py-3 font-medium text-slate-400 text-xs uppercase tracking-wider">Thao tác</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {alerts.map((alert) => {
                        const ti = alert.threat_intel
                        const isCampaign = alert.correlated && alert.severity === 'critical'
                        return (
                        <tr key={alert.alert_id}
                          className={`hover:bg-slate-800/40 cursor-pointer transition-colors ${
                            isCampaign ? 'border-l-2 border-l-red-500' : ''
                          }`}
                          onClick={() => setSelectedAlert(alert)}>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-1.5">
                              <span className="font-medium text-slate-200">{alert.attack_type}</span>
                              {isCampaign && (
                                <span title="Attack Campaign" className="text-xs bg-red-900/40 text-red-300 border border-red-700 px-1.5 py-0.5 rounded font-medium">
                                  CAMPAIGN
                                </span>
                              )}
                              {alert.correlated && !isCampaign && (
                                <Shield className="w-3 h-3 text-orange-400 shrink-0" title="Correlated alert" />
                              )}
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-1.5">
                              <span className="text-slate-400 font-mono text-xs">{alert.source_ip}</span>
                              {ti && ti.threat_level !== 'safe' && (
                                <span className={`text-xs px-1 py-0.5 rounded border font-medium ${
                                  ti.threat_level === 'critical' ? 'bg-red-900/40 text-red-300 border-red-700' :
                                  ti.threat_level === 'high'     ? 'bg-orange-900/40 text-orange-300 border-orange-700' :
                                  ti.threat_level === 'medium'   ? 'bg-yellow-900/40 text-yellow-300 border-yellow-700' :
                                  'bg-slate-800 text-slate-400 border-slate-700'
                                }`} title={`Abuse score: ${ti.abuse_score}%`}>
                                  {ti.is_tor ? '🧅TOR' : ti.is_vpn ? '🔒VPN' : `TI:${ti.abuse_score}%`}
                                </span>
                              )}
                              {alert.threat_intel?.country_code && (
                                <span className="text-xs text-slate-500">
                                  <Globe className="w-3 h-3 inline mr-0.5" />{alert.threat_intel.country_code}
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="px-4 py-3"><SeverityBadge severity={alert.severity} /></td>
                          <td className="px-4 py-3 text-slate-400">{((alert.confidence ?? 0) * 100).toFixed(1)}%</td>
                          <td className="px-4 py-3 text-slate-500 text-xs">{formatDatetime(alert.timestamp)}</td>
                          <td className="px-4 py-3">
                            <span className={`text-xs font-medium ${alert.is_resolved ? 'text-emerald-400' : 'text-amber-400'}`}>
                              {alert.is_resolved ? '✓ Đã xử lý' : '● Đang hoạt động'}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex gap-1">
                              <button onClick={(e) => { e.stopPropagation(); setSelectedAlert(alert) }}
                                className="p-1.5 bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 rounded border border-blue-500/20 transition-colors" title="Xem chi tiết">
                                <Eye className="w-4 h-4" />
                              </button>
                              {!alert.is_resolved && hasRole(['admin', 'security_analyst']) && (
                                <button onClick={(e) => handleResolve(alert.alert_id, e)}
                                  className="p-1.5 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 rounded border border-emerald-500/20 transition-colors" title="Đánh dấu đã xử lý">
                                  <CheckCircle className="w-4 h-4" />
                                </button>
                              )}
                              {hasRole(['admin']) && (
                                <button onClick={(e) => handleDelete(alert.alert_id, e)}
                                  className="p-1.5 bg-red-500/10 text-red-400 hover:bg-red-500/20 rounded border border-red-500/20 transition-colors" title="Xóa">
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={currentPage}
                  totalPages={totalPages}
                  onPageChange={setCurrentPage}
                  pageSize={pageSize}
                  onPageSizeChange={(newSize) => {
                    setPageSize(newSize)
                    setCurrentPage(1)
                  }}
                />
              </>
            )}
          </div>
        </div>

        {/* ── PHẢI: Live Alert Feed (1/3) ── */}
        <div className="flex-1 min-w-[260px] max-w-[340px] flex flex-col bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 overflow-hidden">
          {/* Header live feed */}
          <div className="px-4 py-3 border-b border-slate-800/60 flex items-center justify-between bg-slate-800/40">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
              <span className="text-sm font-semibold text-slate-200">Live Alert Feed</span>
            </div>
            {liveCount > 0 && (
              <span className="text-xs bg-red-500/15 text-red-400 border border-red-500/30 px-2 py-0.5 rounded-full font-medium">
                +{liveCount} mới
              </span>
            )}
          </div>

          {/* Live list */}
          <div className="flex-1 overflow-y-auto divide-y divide-slate-800/60">
            {liveAlerts.length > 0 ? (
              liveAlerts.map((alert, i) => (
                <div key={i}
                  className={`px-4 py-3 border-l-4 cursor-pointer hover:bg-slate-800/40 transition-all ${SEVERITY_LEFT_COLORS[alert.severity] || 'border-l-slate-600'}`}
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
                      <p className="text-sm font-semibold text-slate-200 truncate">{alert.attack_type}</p>
                      <p className="text-xs text-slate-500 font-mono truncate">{alert.src_ip}</p>
                      <p className="text-xs text-slate-600 mt-0.5">{formatDatetime(alert.timestamp)}</p>
                    </div>
                    <SeverityBadge severity={alert.severity} />
                  </div>
                  {alert.confidence && (
                    <div className="mt-1.5">
                      <div className="w-full bg-slate-800 rounded-full h-1">
                        <div
                          className="h-1 rounded-full bg-red-400 transition-all"
                          style={{ width: `${Math.round(alert.confidence * 100)}%` }}
                        />
                      </div>
                      <p className="text-xs text-slate-600 mt-0.5">{Math.round(alert.confidence * 100)}% confidence</p>
                    </div>
                  )}
                </div>
              ))
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center p-6 text-center h-full min-h-[200px]">
                <Activity className="w-10 h-10 text-slate-700 mb-3" />
                <p className="text-sm text-slate-500">Chưa có alert real-time</p>
                <p className="text-xs text-slate-600 mt-1">
                  Chạy demo để xem luồng tấn công
                </p>
                <div className="mt-4 px-3 py-2 bg-slate-800/60 border border-slate-700 rounded-lg text-xs text-slate-500 font-mono">
                  .\demo.ps1 -Action demo-start
                </div>
              </div>
            )}
          </div>

          {/* Footer stats */}
          {liveAlerts.length > 0 && (
            <div className="px-4 py-2 border-t border-slate-800/60 bg-slate-800/30 flex justify-between text-xs text-slate-500">
              <span>{liveAlerts.length} alerts</span>
              <button
                onClick={() => { setLiveAlerts([]); setLiveCount(0) }}
                className="text-slate-500 hover:text-red-400 transition-colors"
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
