import { useEffect, useState } from 'react'
import { History, Shield } from 'lucide-react'
import { fetchAuditLogs } from '../lib/api'
import { formatDatetime } from '../lib/datetime'
import Pagination from '../components/Pagination'

const ACTION_LABELS = {
  login: 'Đăng nhập',
  logout: 'Đăng xuất',
  change_password: 'Đổi mật khẩu',
  create_server: 'Thêm server',
  delete_server: 'Xóa server',
}

export default function AuditLogs() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [actionFilter, setActionFilter] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)
  const [total, setTotal] = useState(0)

  useEffect(() => {
    setLoading(true)
    const params = { limit: pageSize, skip: (currentPage - 1) * pageSize }
    if (actionFilter) params.action = actionFilter
    fetchAuditLogs(params)
      .then((data) => {
        setLogs(data.items || data)
        setTotal(data.total || data.length || 0)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [currentPage, pageSize])

  useEffect(() => {
    setCurrentPage(1)
    setLoading(true)
    const params = { limit: pageSize, skip: 0 }
    if (actionFilter) params.action = actionFilter
    fetchAuditLogs(params)
      .then((data) => {
        setLogs(data.items || data)
        setTotal(data.total || data.length || 0)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [actionFilter])

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20">
            <History className="w-6 h-6 text-amber-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-100">Audit Log</h1>
            <p className="text-sm text-slate-500">Lịch sử thao tác người dùng</p>
          </div>
        </div>
        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-amber-500"
        >
          <option value="">Tất cả hành động</option>
          {Object.entries(ACTION_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
      </div>

      <div className="bg-slate-900/60 backdrop-blur-sm border border-slate-800/60 rounded-xl overflow-hidden">
        {loading ? (
          <p className="p-6 text-slate-400">Đang tải...</p>
        ) : (
          <>
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-800/80 text-xs uppercase text-slate-400 border-b border-slate-700/60">
                <tr>
                  <th className="px-4 py-3">Thời gian</th>
                  <th className="px-4 py-3">User</th>
                  <th className="px-4 py-3">Hành động</th>
                  <th className="px-4 py-3">Resource</th>
                  <th className="px-4 py-3">Chi tiết</th>
                  <th className="px-4 py-3">IP</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {logs.length === 0 ? (
                  <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-500">Chưa có audit log</td></tr>
                ) : logs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="px-4 py-2 text-xs text-slate-400">{formatDatetime(log.created_at)}</td>
                    <td className="px-4 py-2 font-medium text-slate-200">{log.username}</td>
                    <td className="px-4 py-2">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 text-xs">
                        <Shield className="w-3 h-3" />
                        {ACTION_LABELS[log.action] || log.action}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-xs text-slate-400">
                      {log.resource_type ? `${log.resource_type}${log.resource_id ? ` #${log.resource_id}` : ''}` : '—'}
                    </td>
                    <td className="px-4 py-2 text-[10px] font-mono text-slate-400 max-w-[200px] truncate">
                      {log.details ? JSON.stringify(log.details) : '—'}
                    </td>
                    <td className="px-4 py-2 font-mono text-xs text-slate-400">{log.client_ip || '—'}</td>
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
          </>
        )}
      </div>
    </div>
  )
}
