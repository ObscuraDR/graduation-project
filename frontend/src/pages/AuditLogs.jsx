import { useEffect, useState } from 'react'
import { History, Shield } from 'lucide-react'
import { fetchAuditLogs } from '../lib/api'
import { formatDatetime } from '../lib/datetime'

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

  useEffect(() => {
    setLoading(true)
    const params = { limit: 200 }
    if (actionFilter) params.action = actionFilter
    fetchAuditLogs(params)
      .then(setLogs)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [actionFilter])

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <History className="w-8 h-8 text-amber-500" />
          <div>
            <h1 className="text-2xl font-bold text-white">Audit Log</h1>
            <p className="text-sm text-gray-400">Lịch sử thao tác người dùng</p>
          </div>
        </div>
        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white"
        >
          <option value="">Tất cả hành động</option>
          {Object.entries(ACTION_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
      </div>

      <div className="bg-gray-800 border border-gray-700 rounded-xl overflow-hidden">
        {loading ? (
          <p className="p-6 text-gray-400">Đang tải...</p>
        ) : (
          <table className="w-full text-left text-sm text-gray-300">
            <thead className="bg-gray-900/60 text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3">Thời gian</th>
                <th className="px-4 py-3">User</th>
                <th className="px-4 py-3">Hành động</th>
                <th className="px-4 py-3">Resource</th>
                <th className="px-4 py-3">Chi tiết</th>
                <th className="px-4 py-3">IP</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {logs.length === 0 ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-500">Chưa có audit log</td></tr>
              ) : logs.map((log) => (
                <tr key={log.id} className="hover:bg-gray-750">
                  <td className="px-4 py-2 text-xs">{formatDatetime(log.created_at)}</td>
                  <td className="px-4 py-2 font-medium text-white">{log.username}</td>
                  <td className="px-4 py-2">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-amber-600/20 text-amber-300 text-xs">
                      <Shield className="w-3 h-3" />
                      {ACTION_LABELS[log.action] || log.action}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-xs text-gray-400">
                    {log.resource_type ? `${log.resource_type}${log.resource_id ? ` #${log.resource_id}` : ''}` : '—'}
                  </td>
                  <td className="px-4 py-2 text-[10px] font-mono text-gray-500 max-w-[200px] truncate">
                    {log.details ? JSON.stringify(log.details) : '—'}
                  </td>
                  <td className="px-4 py-2 font-mono text-xs">{log.client_ip || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
