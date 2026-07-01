import { useEffect, useState } from 'react'
import { ScrollText, Search, Filter, Play, Pause } from 'lucide-react'
import { fetchSecurityLogs } from '../lib/api'
import { formatDatetime } from '../lib/datetime'
import Pagination from '../components/Pagination'

const LOG_SOURCES = ['', 'auth.log', 'nginx', 'windows', 'unknown']
const EVENT_TYPES = ['', 'ssh_login_failed', 'generic', 'auth', 'security']

export default function LogViewer() {
  const [logs, setLogs] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [refreshInterval, setRefreshInterval] = useState(30) // seconds
  const [filters, setFilters] = useState({
    search: '',
    source_ip: '',
    event_type: '',
    log_source: '',
    server: '',
  })
  const [selected, setSelected] = useState(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)

  const loadLogs = async () => {
    setLoading(true)
    try {
      const params = { limit: pageSize, skip: (currentPage - 1) * pageSize }
      Object.entries(filters).forEach(([k, v]) => {
        if (v) params[k] = v
      })
      const data = await fetchSecurityLogs(params)
      setLogs(data.items || [])
      setTotal(data.total || 0)
    } catch (err) {
      console.error(err)
    }
    setLoading(false)
  }

  useEffect(() => {
    loadLogs()
  }, [currentPage, pageSize])

  useEffect(() => {
    setCurrentPage(1)
    loadLogs()
  }, [filters])

  // Auto-refresh effect
  useEffect(() => {
    if (!autoRefresh) return

    const interval = setInterval(() => {
      loadLogs()
    }, refreshInterval * 1000)

    return () => clearInterval(interval)
  }, [autoRefresh, refreshInterval])

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ScrollText className="w-8 h-8 text-emerald-500" />
          <div>
            <h1 className="text-2xl font-bold text-slate-100">Log Viewer</h1>
            <p className="text-sm text-slate-400">Tập trung log bảo mật — {total} bản ghi</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Auto-refresh toggle */}
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`flex items-center gap-2 px-4 py-2 border rounded-lg text-sm ${
              autoRefresh
                ? 'bg-emerald-600 border-emerald-600 text-white hover:bg-emerald-500'
                : 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700'
            } transition-colors`}
          >
            {autoRefresh ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            {autoRefresh ? 'Auto-refreshing' : 'Auto-refresh off'}
          </button>

          {/* Refresh interval selector */}
          {autoRefresh && (
            <select
              value={refreshInterval}
              onChange={(e) => setRefreshInterval(parseInt(e.target.value))}
              className="px-3 py-2 border border-slate-700 rounded-lg text-sm bg-slate-800 text-slate-300 focus:outline-none focus:border-blue-500"
            >
              <option value={15}>15s</option>
              <option value={30}>30s</option>
              <option value={60}>1m</option>
              <option value={120}>2m</option>
            </select>
          )}
        </div>
      </div>

      <div className="bg-slate-900/60 backdrop-blur-sm border border-slate-800/60 rounded-xl p-4 grid grid-cols-1 md:grid-cols-5 gap-3">
        <input
          placeholder="Tìm kiếm..."
          value={filters.search}
          onChange={(e) => setFilters({ ...filters, search: e.target.value })}
          className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-300 placeholder-slate-500 focus:outline-none focus:border-blue-500"
        />
        <input
          placeholder="Source IP"
          value={filters.source_ip}
          onChange={(e) => setFilters({ ...filters, source_ip: e.target.value })}
          className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-300 placeholder-slate-500 focus:outline-none focus:border-blue-500"
        />
        <select
          value={filters.event_type}
          onChange={(e) => setFilters({ ...filters, event_type: e.target.value })}
          className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-blue-500"
        >
          {EVENT_TYPES.map((t) => (
            <option key={t || 'all'} value={t}>{t || 'All event types'}</option>
          ))}
        </select>
        <select
          value={filters.log_source}
          onChange={(e) => setFilters({ ...filters, log_source: e.target.value })}
          className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-blue-500"
        >
          {LOG_SOURCES.map((s) => (
            <option key={s || 'all'} value={s}>{s || 'All sources'}</option>
          ))}
        </select>
        <button
          type="button"
          onClick={loadLogs}
          disabled={loading}
          className="flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50"
        >
          <Search className="w-4 h-4" /> {loading ? 'Đang tải...' : 'Lọc'}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-slate-900/60 backdrop-blur-sm border border-slate-800/60 rounded-xl overflow-hidden">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-800/80 border-b border-slate-700/60 text-xs uppercase text-slate-400 tracking-wider">
              <tr>
                <th className="px-4 py-3">Thời gian</th>
                <th className="px-4 py-3">Server</th>
                <th className="px-4 py-3">Source IP</th>
                <th className="px-4 py-3">Quốc gia</th>
                <th className="px-4 py-3">Loại</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {logs.length === 0 ? (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-600">Không có log</td></tr>
              ) : logs.map((log) => (
                <tr
                  key={log._id}
                  className="hover:bg-slate-800/40 cursor-pointer transition-colors"
                  onClick={() => setSelected(log)}
                >
                  <td className="px-4 py-2 text-xs text-slate-400">{formatDatetime(log.timestamp)}</td>
                  <td className="px-4 py-2 text-slate-300">{log.server || '—'}</td>
                  <td className="px-4 py-2 font-mono text-blue-400">{log.source_ip || '—'}</td>
                  <td className="px-4 py-2 text-slate-300">{log.country || '—'}</td>
                  <td className="px-4 py-2 text-slate-300">{log.event_type}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pagination
            currentPage={currentPage}
            totalPages={Math.ceil(total / pageSize)}
            onPageChange={setCurrentPage}
            pageSize={pageSize}
            onPageSizeChange={(newSize) => {
              setPageSize(newSize)
              setCurrentPage(1)
            }}
          />
        </div>

        <div className="bg-slate-900/60 backdrop-blur-sm border border-slate-800/60 rounded-xl p-4">
          <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
            <Filter className="w-4 h-4 text-slate-400" /> Chi tiết log
          </h3>
          {selected ? (
            <div className="space-y-2 text-sm">
              <p><span className="text-slate-400">Message:</span> <span className="text-slate-300">{selected.message}</span></p>
              <p><span className="text-slate-400">Source:</span> <span className="text-slate-300">{selected.log_source}</span></p>
              <p><span className="text-slate-400">Server:</span> <span className="text-slate-300">{selected.server}</span></p>
              {selected.raw && (
                <pre className="mt-2 p-2 bg-slate-950 border border-slate-800/60 rounded text-xs text-slate-400 overflow-x-auto whitespace-pre-wrap">{selected.raw}</pre>
              )}
            </div>
          ) : (
            <p className="text-slate-500 text-sm">Chọn một dòng log để xem chi tiết</p>
          )}
        </div>
      </div>
    </div>
  )
}
