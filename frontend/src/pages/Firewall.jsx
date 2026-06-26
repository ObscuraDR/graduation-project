import React, { useEffect, useState } from 'react';
import { ShieldAlert, Trash2, Clock, Plus, History } from 'lucide-react';
import {
  fetchBlacklist, removeBlacklist, addBlacklistWithDuration, fetchBlockHistory,
} from '../lib/api';
import { hasRole } from '../lib/auth';
import { formatDatetime } from '../lib/datetime';

const BLOCK_PRESETS = [
  { label: '1 giờ', hours: 1 },
  { label: '24 giờ', hours: 24 },
  { label: '7 ngày', hours: 168 },
  { label: 'Vĩnh viễn', hours: null },
];

export default function Firewall() {
  const [blacklist, setBlacklist] = useState([]);
  const [history, setHistory] = useState([]);
  const [tab, setTab] = useState('active');
  const [newIp, setNewIp] = useState('');
  const [newReason, setNewReason] = useState('');
  const [presetHours, setPresetHours] = useState(24);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadBlacklist();
    loadHistory();
  }, []);

  const loadBlacklist = async () => {
    try {
      const data = await fetchBlacklist();
      setBlacklist(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to fetch blacklist:', err);
    }
  };

  const loadHistory = async () => {
    try {
      const data = await fetchBlockHistory(50);
      setHistory(Array.isArray(data) ? data : []);
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

  const handleAddBlock = async (hours = presetHours) => {
    if (!newIp.trim()) return;
    setError('');
    setLoading(true);
    try {
      await addBlacklistWithDuration(newIp.trim(), newReason || 'Manual block', hours);
      setNewIp('');
      setNewReason('');
      loadBlacklist();
      loadHistory();
    } catch (err) {
      setError(err.response?.data?.detail || 'Không thể thêm IP vào blacklist');
    } finally {
      setLoading(false);
    }
  };

  const canManage = hasRole(['admin', 'security_analyst']);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <ShieldAlert className="w-8 h-8 text-red-500" />
        <h1 className="text-2xl font-bold text-white">Quản lý Firewall</h1>
      </div>

      {error && (
        <div className="bg-red-900/40 border border-red-600 text-red-300 rounded-lg px-4 py-3 text-sm">
          {error}
          <button onClick={() => setError('')} className="ml-3 underline text-xs">Đóng</button>
        </div>
      )}

      {canManage && (
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-4 space-y-3">
          <h2 className="text-sm font-semibold text-white">Chặn IP tạm thời</h2>
          <div className="flex flex-wrap gap-2">
            {BLOCK_PRESETS.map((p) => (
              <button
                key={p.label}
                type="button"
                onClick={() => setPresetHours(p.hours)}
                className={`px-3 py-1.5 text-xs rounded-lg border ${
                  presetHours === p.hours
                    ? 'bg-red-600 border-red-600 text-white'
                    : 'border-gray-600 text-gray-300 hover:border-red-400'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            <input
              value={newIp}
              onChange={(e) => setNewIp(e.target.value)}
              placeholder="113.22.45.12"
              className="flex-1 min-w-[140px] bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm font-mono"
            />
            <input
              value={newReason}
              onChange={(e) => setNewReason(e.target.value)}
              placeholder="Lý do"
              className="flex-1 min-w-[140px] bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
            />
            <button
              type="button"
              onClick={() => handleAddBlock(presetHours)}
              disabled={loading || !newIp.trim()}
              className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium"
            >
              <Plus className="w-4 h-4" /> {loading ? 'Đang chặn...' : 'Chặn'}
            </button>
          </div>
        </div>
      )}

      <div className="flex gap-2 border-b border-gray-700">
        {[
          { id: 'active', label: 'Đang chặn' },
          { id: 'history', label: 'Lịch sử block' },
        ].map(({ id, label }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
              tab === id ? 'border-red-500 text-red-400' : 'border-transparent text-gray-500'
            }`}
          >
            {id === 'history' && <History className="w-4 h-4 inline mr-1" />}
            {label}
          </button>
        ))}
      </div>

      {tab === 'active' ? (
        <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
          <table className="w-full text-left text-gray-300">
            <thead className="bg-gray-900/50 text-gray-400 text-xs uppercase">
              <tr>
                <th className="px-6 py-4">IP</th>
                <th className="px-6 py-4">Lý do</th>
                <th className="px-6 py-4">Thời gian chặn</th>
                <th className="px-6 py-4">Hết hạn</th>
                <th className="px-6 py-4 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {blacklist.length === 0 ? (
                <tr><td colSpan={5} className="px-6 py-8 text-center text-gray-500">Không có IP bị chặn</td></tr>
              ) : blacklist.map((item) => (
                <tr key={item.ip_address}>
                  <td className="px-6 py-4 font-mono text-blue-400">{item.ip_address}</td>
                  <td className="px-6 py-4 text-sm">{item.reason || '—'}</td>
                  <td className="px-6 py-4 text-xs">{formatDatetime(item.created_at)}</td>
                  <td className="px-6 py-4 text-xs text-orange-400">
                    <Clock className="w-3 h-3 inline mr-1" />
                    {item.expires_at ? formatDatetime(item.expires_at) : 'Vĩnh viễn'}
                  </td>
                  <td className="px-6 py-4 text-right">
                    {canManage && (
                      <button type="button" onClick={() => handleUnblock(item.ip_address)} className="text-red-400 hover:text-red-300">
                        <Trash2 className="w-5 h-5" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
          <table className="w-full text-left text-gray-300 text-sm">
            <thead className="bg-gray-900/50 text-gray-400 text-xs uppercase">
              <tr>
                <th className="px-6 py-4">Thời gian</th>
                <th className="px-6 py-4">IP</th>
                <th className="px-6 py-4">Hành động</th>
                <th className="px-6 py-4">Thời hạn</th>
                <th className="px-6 py-4">Lý do</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {history.map((h) => (
                <tr key={h.id}>
                  <td className="px-6 py-3 text-xs">{formatDatetime(h.created_at)}</td>
                  <td className="px-6 py-3 font-mono text-blue-400">{h.ip_address}</td>
                  <td className="px-6 py-3">
                    <span className={h.action === 'block' ? 'text-red-400' : 'text-green-400'}>{h.action}</span>
                  </td>
                  <td className="px-6 py-3">{h.duration_hours ? `${h.duration_hours}h` : h.action === 'block' ? '∞' : '—'}</td>
                  <td className="px-6 py-3 text-gray-400">{h.reason || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
