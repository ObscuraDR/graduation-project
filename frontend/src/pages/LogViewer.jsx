import { useEffect, useState } from 'react'
import { ScrollText, Search, Filter } from 'lucide-react'
import { fetchSecurityLogs } from '../lib/api'
import { formatDatetime } from '../lib/datetime'
import Pagination from '../components/Pagination'

const LOG_SOURCES = ['', 'auth.log', 'nginx', 'windows', 'unknown']
const EVENT_TYPES = ['', 'ssh_login_failed', 'generic', 'auth', 'security']

export default function LogViewer() {
  const [logs, setLogs] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
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

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <ScrollText className="w-8 h-8 text-emerald-500" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Log Viewer</h1>
          <p className="text-sm text-gray-500">Tập trung log bảo mật — {total} bản ghi</p>
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-xl p-4 grid grid-cols-1 md:grid-cols-5 gap-3">
        <input
          placeholder="Tìm kiếm..."
          value={filters.search}
          onChange={(e) => setFilters({ ...filters, search: e.target.value })}
          className="bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-700"
        />
        <input
          placeholder="Source IP"
          value={filters.source_ip}
          onChange={(e) => setFilters({ ...filters, source_ip: e.target.value })}
          className="bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-700"
        />
        <select
          value={filters.event_type}
          onChange={(e) => setFilters({ ...filters, event_type: e.target.value })}
          className="bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-700"
        >
          {EVENT_TYPES.map((t) => (
            <option key={t || 'all'} value={t}>{t || 'All event types'}</option>
          ))}
        </select>
        <select
          value={filters.log_source}
          onChange={(e) => setFilters({ ...filters, log_source: e.target.value })}
          className="bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-700"
        >
          {LOG_SOURCES.map((s) => (
            <option key={s || 'all'} value={s}>{s || 'All sources'}</option>
          ))}
        </select>
        <button
          type="button"
          onClick={loadLogs}
          disabled={loading}
          className="flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg px-4 py-2 text-sm font-medium"
        >
          <Search className="w-4 h-4" /> {loading ? 'Đang tải...' : 'Lọc'}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white border border-gray-100 rounded-xl overflow-hidden">
          <table className="w-full text-left text-sm text-gray-700">
            <thead className="bg-gray-50 text-xs uppercase text-gray-600">
              <tr>
                <th className="px-4 py-3">Thời gian</th>
                <th className="px-4 py-3">Server</th>
                <th className="px-4 py-3">Source IP</th>
                <th className="px-4 py-3">Quốc gia</th>
                <th className="px-4 py-3">Loại</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {logs.length === 0 ? (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-500">Không có log</td></tr>
              ) : logs.map((log) => (
                <tr
                  key={log._id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => setSelected(log)}
                >
                  <td className="px-4 py-2 text-xs text-gray-600">{formatDatetime(log.timestamp)}</td>
                  <td className="px-4 py-2 text-gray-700">{log.server || '—'}</td>
                  <td className="px-4 py-2 font-mono text-blue-600">{log.source_ip || '—'}</td>
                  <td className="px-4 py-2 text-gray-700">{log.country || '—'}</td>
                  <td className="px-4 py-2 text-gray-700">{log.event_type}</td>
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

        <div className="bg-white border border-gray-100 rounded-xl p-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-500" /> Chi tiết log
          </h3>
          {selected ? (
            <div className="space-y-2 text-sm">
              <p><span className="text-gray-500">Message:</span> <span className="text-gray-700">{selected.message}</span></p>
              <p><span className="text-gray-500">Source:</span> {selected.log_source}</p>
              <p><span className="text-gray-500">Server:</span> {selected.server}</p>
              {selected.raw && (
                <pre className="mt-2 p-2 bg-gray-900 rounded text-xs text-gray-400 overflow-x-auto whitespace-pre-wrap">{selected.raw}</pre>
              )}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">Chọn một dòng log để xem chi tiết</p>
          )}
        </div>
      </div>
    </div>
  )
}
