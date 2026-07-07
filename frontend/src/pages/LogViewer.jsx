import { useEffect, useState } from 'react'
import { ScrollText, Search, Play, Pause, Server, AlertTriangle, RefreshCw } from 'lucide-react'
import { fetchSecurityLogs } from '../lib/api'
import api from '../lib/api'
import { formatDatetime } from '../lib/datetime'

// Event type → màu badge
const EVENT_BADGE = {
  ssh_brute_force:    { color: 'bg-red-900/40 text-red-300 border-red-800',      label: 'SSH Brute Force' },
  cpu_spike:          { color: 'bg-orange-900/40 text-orange-300 border-orange-800', label: 'CPU Spike' },
  ram_spike:          { color: 'bg-yellow-900/40 text-yellow-300 border-yellow-800', label: 'RAM Spike' },
  syn_flood_inbound:  { color: 'bg-red-900/40 text-red-300 border-red-800',      label: 'SYN Flood (In)' },
  syn_flood_outbound: { color: 'bg-orange-900/40 text-orange-300 border-orange-800', label: 'SYN Flood (Out)' },
  generic:            { color: 'bg-slate-800 text-slate-400 border-slate-700',   label: 'Generic' },
}

const SEVERITY_BADGE = {
  critical: 'bg-red-900/50 text-red-300 border-red-700',
  high:     'bg-orange-900/50 text-orange-300 border-orange-700',
  medium:   'bg-yellow-900/50 text-yellow-300 border-yellow-700',
  low:      'bg-green-900/50 text-green-300 border-green-700',
}

const ALL_EVENT_TYPES = [
  '', 'ssh_brute_force', 'cpu_spike', 'ram_spike',
  'syn_flood_inbound', 'syn_flood_outbound', 'generic',
]
const ALL_LOG_SOURCES = ['', 'auth.log', 'psutil', 'psutil.net_connections', 'agent', 'sniffer']

export default function LogViewer() {
  const [logs, setLogs] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [refreshInterval, setRefreshInterval] = useState(30)
  const [servers, setServers] = useState([])  // danh sách servers để filter
  const [filters, setFilters] = useState({
    search: '',
    source_ip: '',
    event_type: '',
    log_source: '',
    server: '',
  })
  const [selected, setSelected] = useState(null)
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 50

  // Load danh sách servers để hiện trong filter
  useEffect(() => {
    api.get('/servers').then(res => {
      setServers(res.data || [])
    }).catch(() => {})
  }, [])

  const loadLogs = async (currentPage = page) => {
    setLoading(true)
    try {
      const params = { limit: PAGE_SIZE, skip: (currentPage - 1) * PAGE_SIZE }
      Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v })
      const data = await fetchSecurityLogs(params)
      setLogs(data.items || [])
      setTotal(data.total || 0)
    } catch (err) {
      console.error(err)
    }
    setLoading(false)
  }

  useEffect(() => { loadLogs(page) }, [page])
  useEffect(() => { setPage(1); loadLogs(1) }, [filters])

  useEffect(() => {
    if (!autoRefresh) return
    const interval = setInterval(() => loadLogs(page), refreshInterval * 1000)
    return () => clearInterval(interval)
  }, [autoRefresh, refreshInterval, page, filters])

  const totalPages = Math.ceil(total / PAGE_SIZE)

  const getEventBadge = (eventType) =>
    EVENT_BADGE[eventType] || { color: 'bg-slate-800 text-slate-400 border-slate-700', label: eventType }

  return (
    <div className="p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
            <ScrollText className="w-6 h-6 text-emerald-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-100">Log Viewer</h1>
            <p className="text-sm text-slate-500">
              Log bảo mật tập trung từ tất cả máy chủ — <span className="text-emerald-400">{total}</span> bản ghi
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {autoRefresh && (
            <select value={refreshInterval}
              onChange={(e) => setRefreshInterval(parseInt(e.target.value))}
              className="px-2 py-1.5 border border-slate-700 rounded-lg text-xs bg-slate-800 text-slate-300">
              <option value={15}>15s</option>
              <option value={30}>30s</option>
              <option value={60}>1m</option>
            </select>
          )}
          <button onClick={() => setAutoRefresh(!autoRefresh)}
            className={`flex items-center gap-2 px-3 py-1.5 border rounded-lg text-sm transition-colors ${
              autoRefresh
                ? 'bg-emerald-600 border-emerald-600 text-white'
                : 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700'
            }`}>
            {autoRefresh ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            {autoRefresh ? 'Live' : 'Auto'}
          </button>
          <button onClick={() => loadLogs(page)} disabled={loading}
            className="flex items-center gap-1 px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-300 hover:bg-slate-700 disabled:opacity-50">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-slate-900/60 border border-slate-800/60 rounded-xl p-4 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <input placeholder="Tìm kiếm message..."
          value={filters.search}
          onChange={(e) => setFilters({ ...filters, search: e.target.value })}
          className="col-span-2 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-300 placeholder-slate-500 focus:outline-none focus:border-emerald-500" />

        <input placeholder="Source IP"
          value={filters.source_ip}
          onChange={(e) => setFilters({ ...filters, source_ip: e.target.value })}
          className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-300 placeholder-slate-500 focus:outline-none focus:border-emerald-500 font-mono" />

        {/* Filter theo server */}
        <select value={filters.server}
          onChange={(e) => setFilters({ ...filters, server: e.target.value })}
          className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-emerald-500">
          <option value="">Tất cả máy chủ</option>
          <option value="local">Local (IDS)</option>
          {servers.map(s => (
            <option key={s.id} value={s.name}>{s.name}</option>
          ))}
        </select>

        <select value={filters.event_type}
          onChange={(e) => setFilters({ ...filters, event_type: e.target.value })}
          className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-emerald-500">
          {ALL_EVENT_TYPES.map(t => (
            <option key={t || 'all'} value={t}>
              {t ? (EVENT_BADGE[t]?.label || t) : 'Tất cả loại'}
            </option>
          ))}
        </select>

        <select value={filters.log_source}
          onChange={(e) => setFilters({ ...filters, log_source: e.target.value })}
          className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-emerald-500">
          {ALL_LOG_SOURCES.map(s => (
            <option key={s || 'all'} value={s}>{s || 'Tất cả nguồn'}</option>
          ))}
        </select>
      </div>

      {/* Main content - split layout */}
      <div className="flex gap-4" style={{ height: 'calc(100vh - 320px)', minHeight: '400px' }}>

        {/* Left: Log table */}
        <div className="flex-[2] bg-slate-900/60 border border-slate-800/60 rounded-xl flex flex-col overflow-hidden">
          <div className="overflow-auto flex-1">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-slate-900 border-b border-slate-800 text-xs uppercase text-slate-500 tracking-wider">
                <tr>
                  <th className="px-4 py-3 text-left">Thời gian</th>
                  <th className="px-4 py-3 text-left">
                    <span className="flex items-center gap-1"><Server className="w-3 h-3" /> Máy chủ</span>
                  </th>
                  <th className="px-4 py-3 text-left">Source IP</th>
                  <th className="px-4 py-3 text-left">Loại sự kiện</th>
                  <th className="px-4 py-3 text-left">Mức độ</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/40">
                {logs.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-16 text-center">
                      <ScrollText className="w-10 h-10 mx-auto mb-3 text-slate-700" />
                      <p className="text-slate-500 text-sm">Không có log nào</p>
                      {filters.server && (
                        <p className="text-slate-600 text-xs mt-1">
                          Chưa có log từ "{filters.server}" — agent có đang chạy không?
                        </p>
                      )}
                    </td>
                  </tr>
                ) : logs.map((log, i) => {
                  const badge = getEventBadge(log.event_type)
                  const severity = log.extra?.severity
                  const isAgent = log.log_source !== 'local' && log.log_source !== 'sniffer'
                  return (
                    <tr key={log.id || i}
                      className={`hover:bg-slate-800/30 cursor-pointer transition-colors ${
                        selected?.id === log.id ? 'bg-slate-800/50 border-l-2 border-l-emerald-500' : ''
                      }`}
                      onClick={() => setSelected(log)}>
                      <td className="px-4 py-2.5 text-xs text-slate-400 whitespace-nowrap">
                        {formatDatetime(log.timestamp)}
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={`inline-flex items-center gap-1 text-xs ${
                          isAgent ? 'text-blue-400' : 'text-slate-300'
                        }`}>
                          <Server className="w-3 h-3 shrink-0" />
                          {log.server || 'local'}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 font-mono text-xs text-blue-300">
                        {log.source_ip || '—'}
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={`inline-block text-xs px-2 py-0.5 rounded border ${badge.color}`}>
                          {badge.label}
                        </span>
                      </td>
                      <td className="px-4 py-2.5">
                        {severity ? (
                          <span className={`inline-block text-xs px-2 py-0.5 rounded border ${SEVERITY_BADGE[severity] || SEVERITY_BADGE.low}`}>
                            {severity.toUpperCase()}
                          </span>
                        ) : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="border-t border-slate-800 px-4 py-3 flex items-center justify-between text-xs text-slate-500">
            <span>{total} bản ghi tổng cộng</span>
            <div className="flex items-center gap-2">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                className="px-2 py-1 bg-slate-800 rounded disabled:opacity-30 hover:bg-slate-700">←</button>
              <span>Trang {page} / {Math.max(1, totalPages)}</span>
              <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages}
                className="px-2 py-1 bg-slate-800 rounded disabled:opacity-30 hover:bg-slate-700">→</button>
            </div>
          </div>
        </div>

        {/* Right: Detail panel */}
        <div className="flex-1 min-w-[260px] max-w-[320px] bg-slate-900/60 border border-slate-800/60 rounded-xl p-4 flex flex-col">
          <h3 className="text-sm font-semibold text-slate-300 mb-3">Chi tiết sự kiện</h3>

          {selected ? (
            <div className="space-y-3 text-sm overflow-y-auto flex-1">
              <div>
                <p className="text-xs text-slate-500 mb-1">Thời gian</p>
                <p className="text-slate-300">{formatDatetime(selected.timestamp)}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500 mb-1">Máy chủ nguồn</p>
                <p className="text-blue-400 font-medium">{selected.server || 'local'}</p>
              </div>
              {selected.source_ip && (
                <div>
                  <p className="text-xs text-slate-500 mb-1">IP tấn công</p>
                  <p className="font-mono text-red-400">{selected.source_ip}</p>
                </div>
              )}
              <div>
                <p className="text-xs text-slate-500 mb-1">Loại sự kiện</p>
                <span className={`inline-block text-xs px-2 py-1 rounded border ${getEventBadge(selected.event_type).color}`}>
                  {getEventBadge(selected.event_type).label}
                </span>
              </div>
              {selected.extra?.severity && (
                <div>
                  <p className="text-xs text-slate-500 mb-1">Mức độ</p>
                  <span className={`inline-block text-xs px-2 py-1 rounded border ${SEVERITY_BADGE[selected.extra.severity] || SEVERITY_BADGE.low}`}>
                    {selected.extra.severity.toUpperCase()}
                  </span>
                </div>
              )}
              {selected.extra?.count && (
                <div>
                  <p className="text-xs text-slate-500 mb-1">Số lần</p>
                  <p className="text-slate-300 font-semibold">{selected.extra.count} lần</p>
                </div>
              )}
              <div>
                <p className="text-xs text-slate-500 mb-1">Mô tả</p>
                <p className="text-slate-300 text-xs leading-relaxed">{selected.message}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500 mb-1">Nguồn log</p>
                <p className="text-slate-400 font-mono text-xs">{selected.log_source}</p>
              </div>
              {selected.raw && (
                <div>
                  <p className="text-xs text-slate-500 mb-1">Raw log</p>
                  <pre className="p-2 bg-slate-950 border border-slate-800 rounded text-xs text-slate-400 overflow-x-auto whitespace-pre-wrap max-h-40">
                    {selected.raw}
                  </pre>
                </div>
              )}
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-600 text-sm">
              <AlertTriangle className="w-8 h-8 mb-2 text-slate-700" />
              <p>Chọn một dòng log</p>
              <p className="text-xs mt-1">để xem chi tiết</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
