import React, { useEffect, useState } from 'react';
import { ShieldAlert, Trash2, Clock, Plus, History } from 'lucide-react';
import {
  fetchBlacklist, removeBlacklist, addBlacklistWithDuration, fetchBlockHistory,
} from '../lib/api';
import { hasRole } from '../lib/auth';
import { formatDatetime } from '../lib/datetime';
import Pagination from '../components/Pagination';
import BlockIPModal from '../components/BlockIPModal';

export default function Firewall() {
  const [blacklist, setBlacklist] = useState([]);
  const [history, setHistory] = useState([]);
  const [tab, setTab] = useState('active');
  const [showBlockIPModal, setShowBlockIPModal] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalBlacklist, setTotalBlacklist] = useState(0);
  const [totalHistory, setTotalHistory] = useState(0);

  useEffect(() => {
    loadBlacklist();
    loadHistory();
  }, [currentPage, pageSize]);

  const loadBlacklist = async () => {
    try {
      const data = await fetchBlacklist({ limit: pageSize, skip: (currentPage - 1) * pageSize });
      setBlacklist(Array.isArray(data.items) ? data.items : (Array.isArray(data) ? data : []));
      setTotalBlacklist(data.total || data.length || 0);
    } catch (err) {
      console.error('Failed to fetch blacklist:', err);
    }
  };

  const loadHistory = async () => {
    try {
      const data = await fetchBlockHistory({ limit: pageSize, skip: (currentPage - 1) * pageSize });
      setHistory(Array.isArray(data.items) ? data.items : (Array.isArray(data) ? data : []));
      setTotalHistory(data.total || data.length || 0);
    } catch (err) {
      console.error('Failed to fetch block history:', err);
    }
  };

  const handleUnblock = async (ip) => {
    if (window.confirm(`Bạn có chắc muốn gỡ chặn IP ${ip}?`)) {
      try {
        await removeBlacklist(ip);
        loadBlacklist();
        loadHistory();
      } catch (err) {
        setError(`Không thể gỡ chặn IP ${ip}: ${err.response?.data?.detail || err.message}`);
      }
    }
  };

  const handleAddBlock = async (data) => {
    setError('');
    setLoading(true);
    try {
      await addBlacklistWithDuration(data.ip_address, data.reason || 'Manual block', data.expires_hours || 24);
      loadBlacklist();
      loadHistory();
      setShowBlockIPModal(false);
    } catch (err) {
      setError(err.response?.data?.detail || 'Không thể thêm IP vào blacklist');
    } finally {
      setLoading(false);
    }
  };

  const canManage = hasRole(['admin', 'security_analyst']);

  const thClass = "text-left px-4 py-3 font-medium text-slate-400 text-xs uppercase tracking-wider";
  const tdClass = "px-4 py-3 text-sm";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2.5 rounded-xl bg-red-500/10 border border-red-500/20">
          <ShieldAlert className="w-6 h-6 text-red-400" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Quản lý Firewall</h1>
          <p className="text-sm text-slate-500 mt-0.5">IP Blacklist & Block History</p>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg px-4 py-3 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError('')} className="ml-3 underline text-xs hover:text-red-300">Đóng</button>
        </div>
      )}

      {canManage && (
        <div className="bg-slate-900/60 backdrop-blur-sm border border-slate-800/60 rounded-xl p-4 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-200">Chặn IP thủ công</h2>
            <p className="text-xs text-slate-500 mt-0.5">Thêm IP vào blacklist với thời gian tùy chọn</p>
          </div>
          <button
            onClick={() => setShowBlockIPModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg text-sm font-medium transition-colors shadow-lg shadow-red-500/20"
          >
            <Plus className="w-4 h-4" /> Chặn IP
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-800/40 p-1 rounded-lg w-fit border border-slate-700/40">
        {[
          { id: 'active', label: 'Đang chặn', count: totalBlacklist },
          { id: 'history', label: 'Lịch sử block', icon: History },
        ].map(({ id, label, icon: Icon, count }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-md transition-all ${
              tab === id
                ? 'bg-slate-700 text-slate-100 shadow-sm'
                : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            {Icon && <Icon className="w-4 h-4" />}
            {label}
            {count != null && tab === 'active' && id === 'active' && count > 0 && (
              <span className="bg-red-500/20 text-red-400 text-xs px-1.5 py-0.5 rounded-full border border-red-500/20">{count}</span>
            )}
          </button>
        ))}
      </div>

      {/* Table */}
      {tab === 'active' ? (
        <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 overflow-hidden">
          <div className="overflow-auto max-h-[calc(100vh-380px)]">
            <table className="w-full text-left">
              <thead className="bg-slate-800/80 border-b border-slate-700/60 sticky top-0">
                <tr>
                  <th className={thClass}>IP</th>
                  <th className={thClass}>Lý do</th>
                  <th className={thClass}>Thời gian chặn</th>
                  <th className={thClass}>Hết hạn</th>
                  {canManage && <th className={`${thClass} text-right`}>Thao tác</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {blacklist.length === 0 ? (
                  <tr><td colSpan={5} className="px-4 py-10 text-center text-slate-600">Không có IP bị chặn</td></tr>
                ) : blacklist.map((item) => (
                  <tr key={item.ip_address} className="hover:bg-slate-800/40 transition-colors">
                    <td className={`${tdClass} font-mono text-blue-400`}>{item.ip_address}</td>
                    <td className={`${tdClass} text-slate-400`}>{item.reason || '—'}</td>
                    <td className={`${tdClass} text-slate-500 text-xs`}>{formatDatetime(item.created_at)}</td>
                    <td className={`${tdClass} text-xs`}>
                      <span className={`flex items-center gap-1 ${item.expires_at ? 'text-amber-400' : 'text-red-400'}`}>
                        <Clock className="w-3 h-3" />
                        {item.expires_at ? formatDatetime(item.expires_at) : 'Vĩnh viễn'}
                      </span>
                    </td>
                    {canManage && (
                      <td className={`${tdClass} text-right`}>
                        <button type="button" onClick={() => handleUnblock(item.ip_address)}
                          className="p-1.5 bg-red-500/10 text-red-400 hover:bg-red-500/20 rounded border border-red-500/20 transition-colors">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            currentPage={currentPage}
            totalPages={Math.ceil(totalBlacklist / pageSize)}
            onPageChange={setCurrentPage}
            pageSize={pageSize}
            onPageSizeChange={(newSize) => { setPageSize(newSize); setCurrentPage(1) }}
          />
        </div>
      ) : (
        <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 overflow-hidden">
          <div className="overflow-auto max-h-[calc(100vh-380px)]">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-800/80 border-b border-slate-700/60 sticky top-0">
                <tr>
                  <th className={thClass}>Thời gian</th>
                  <th className={thClass}>IP</th>
                  <th className={thClass}>Hành động</th>
                  <th className={thClass}>Thời hạn</th>
                  <th className={thClass}>Lý do</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {history.map((h) => (
                  <tr key={h.id} className="hover:bg-slate-800/40 transition-colors">
                    <td className={`${tdClass} text-slate-500 text-xs`}>{formatDatetime(h.created_at)}</td>
                    <td className={`${tdClass} font-mono text-blue-400`}>{h.ip_address}</td>
                    <td className={tdClass}>
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${h.action === 'block' ? 'bg-red-500/10 text-red-400 border-red-500/20' : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'}`}>
                        {h.action}
                      </span>
                    </td>
                    <td className={`${tdClass} text-slate-400`}>{h.duration_hours ? `${h.duration_hours}h` : h.action === 'block' ? '∞' : '—'}</td>
                    <td className={`${tdClass} text-slate-500`}>{h.reason || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            currentPage={currentPage}
            totalPages={Math.ceil(totalHistory / pageSize)}
            onPageChange={setCurrentPage}
            pageSize={pageSize}
            onPageSizeChange={(newSize) => { setPageSize(newSize); setCurrentPage(1) }}
          />
        </div>
      )}

      {/* Block IP Modal */}
      <BlockIPModal
        isOpen={showBlockIPModal}
        onClose={() => setShowBlockIPModal(false)}
        onBlock={handleAddBlock}
      />
    </div>
  );
}
