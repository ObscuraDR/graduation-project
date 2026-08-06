import React, { useEffect, useState, useCallback } from 'react';
import { Server, PlusCircle, Edit, Trash2, Cpu, HardDrive, ShieldCheck, WifiOff, Activity, LineChart as LineChartIcon, AlertTriangle, Shield, ShieldAlert } from 'lucide-react';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { formatDatetime, formatChartTime } from '../lib/datetime';
import { fetchSecurityLogs } from '../lib/api';

const CHART_TOOLTIP_STYLE = {
  background: '#0f172a',
  border: '1px solid #334155',
  borderRadius: '8px',
  color: '#e2e8f0',
}

const inputClass = "w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-slate-200 placeholder-slate-600 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
const labelClass = "block text-sm font-medium text-slate-400 mb-1.5"

export default function ServerManagement() {
  const [servers, setServers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [newServer, setNewServer] = useState({ name: '', ip_address: '', os: '', description: '' });
  const [showEditModal, setShowEditModal] = useState(false);
  const [serverToEdit, setServerToEdit] = useState(null);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [historyData, setHistoryData] = useState([]);
  const [baselines, setBaselines] = useState({});
  // serverEvents: {server_name: [{event_type, severity, message, timestamp}]}
  const [serverEvents, setServerEvents] = useState({});

  useEffect(() => {
    fetchServers();
    // silent=true để không flash loading khi auto-refresh nền
    const intervalId = setInterval(() => fetchServers(true), 10000);
    return () => clearInterval(intervalId);
  }, []);

  const fetchServers = async (silent = false) => {
    if (!silent) setLoading(true);
    setError('');
    try {
      const response = await axios.get('/api/servers');
      setServers(response.data);
      response.data.forEach(server => {
        if (server.status === 'online') {
          // Fetch baseline
          axios.get(`/api/servers/${server.id}/baseline`)
            .then(r => setBaselines(prev => ({ ...prev, [server.id]: r.data })))
            .catch(() => {})
        }
      })
      // Fetch security events cho từng server (5 phút gần nhất)
      fetchServerSecurityEvents(response.data);
    } catch (err) {
      setError('Không thể tải danh sách máy chủ.');
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const fetchServerSecurityEvents = async (serverList) => {
    // Lấy security logs 5 phút gần nhất từ tất cả servers
    try {
      const data = await fetchSecurityLogs({ limit: 50, skip: 0 });
      const items = data.items || [];

      // Nhóm theo server name
      const byServer = {};
      items.forEach(log => {
        if (!log.server || log.server === 'local') return;
        const name = log.server;
        if (!byServer[name]) byServer[name] = [];
        // Chỉ giữ events trong 3 phút gần nhất (giảm từ 5 xuống 3)
        const ts = new Date(log.timestamp);
        const age = (Date.now() - ts.getTime()) / 1000 / 60; // minutes
        if (age <= 3) {
          byServer[name].push({
            event_type: log.event_type,
            severity:   log.extra?.severity || 'low',
            message:    log.message,
            timestamp:  log.timestamp,
            source_ip:  log.source_ip,
          });
        }
      });
      setServerEvents(byServer);
    } catch (err) {
      // Không critical — bỏ qua
    }
  };

  const handleAddServer = async () => {
    try {
      await axios.post('/api/servers', newServer);
      setShowAddModal(false);
      setNewServer({ name: '', ip_address: '', os: '', description: '' });
      fetchServers();
    } catch (err) {
      alert('Lỗi khi thêm máy chủ: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleUpdateServer = async () => {
    if (!serverToEdit) return;
    try {
      await axios.put(`/api/servers/${serverToEdit.id}`, serverToEdit);
      setShowEditModal(false);
      setServerToEdit(null);
      fetchServers();
    } catch (err) {
      alert('Lỗi khi cập nhật máy chủ: ' + (err.response?.data?.detail || err.message));
    }
  };

  const fetchServerHistory = async (serverId) => {
    try {
      const response = await axios.get(`/api/servers/${serverId}/history?limit=50`);
      setHistoryData(response.data.reverse());
    } catch (err) {
      alert('Lỗi khi tải lịch sử máy chủ: ' + (err.response?.data?.detail || err.message));
    }
  };

  const openHistoryModal = (server) => {
    setServerToEdit(server);
    fetchServerHistory(server.id);
    setShowHistoryModal(true);
  };

  const openEditModal = (server) => {
    setServerToEdit({ ...server });
    setShowEditModal(true);
  };

  const handleDeleteServer = async (serverId) => {
    if (window.confirm('Bạn có chắc muốn xóa máy chủ này?')) {
      try {
        await axios.delete(`/api/servers/${serverId}`);
        fetchServers();
      } catch (err) {
        alert('Lỗi khi xóa máy chủ: ' + (err.response?.data?.detail || err.message));
      }
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'online': return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      case 'warning': return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
      case 'offline': return 'bg-red-500/10 text-red-400 border-red-500/20';
      default: return 'bg-slate-500/10 text-slate-400 border-slate-500/20';
    }
  };

  const UsageBar = ({ value, color }) => (
    <div className="w-full bg-slate-800 rounded-full h-1 mt-1">
      <div className={`h-1 rounded-full transition-all ${color}`} style={{ width: `${Math.min(value || 0, 100)}%` }} />
    </div>
  );

  const modalOverlay = "fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4"
  const modalCard = "bg-slate-900 border border-slate-700/60 rounded-2xl shadow-2xl w-full max-w-md"

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-blue-500/10 border border-blue-500/20">
            <Server className="w-6 h-6 text-blue-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-100">Quản lý Máy chủ</h1>
            <p className="text-sm text-slate-500 mt-0.5">{servers.length} máy chủ đang quản lý</p>
          </div>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-medium transition-colors shadow-lg shadow-blue-500/20"
        >
          <PlusCircle className="w-5 h-5" /> Thêm Máy chủ
        </button>
      </div>

      {loading && <p className="text-slate-500 text-sm">Đang tải danh sách máy chủ...</p>}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg px-4 py-3 text-sm">{error}</div>
      )}
      {!loading && !error && servers.length === 0 && (
        <div className="bg-slate-900/60 border border-slate-800/60 rounded-xl p-12 text-center">
          <Server className="w-12 h-12 mx-auto mb-3 text-slate-700" />
          <p className="text-slate-500">Chưa có máy chủ nào được thêm.</p>
        </div>
      )}

      {/* Server Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {servers.map((server) => (
          <div key={server.id} className="bg-slate-900/60 backdrop-blur-sm p-5 rounded-xl border border-slate-800/60 hover:border-slate-700/60 transition-all">
            <div className="flex items-start justify-between mb-4">
              <h2 className="text-base font-semibold text-slate-100">{server.name}</h2>
              <div className="flex items-center gap-1.5">
                {baselines[server.id] && baselines[server.id].cpu && (
                  <span title={`Baseline CPU: ${baselines[server.id].cpu?.mean}% ±${baselines[server.id].cpu?.stdev}%`}
                    className="text-xs bg-blue-900/30 text-blue-400 border border-blue-800/60 px-1.5 py-0.5 rounded">
                    BL
                  </span>
                )}
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getStatusBadge(server.status)}`}>
                  {server.status?.toUpperCase()}
                </span>
              </div>
            </div>

            {/* Attack indicator — hiển thị nếu có events trong 5 phút gần nhất */}
            {serverEvents[server.name] && serverEvents[server.name].length > 0 && (() => {
              const events = serverEvents[server.name];
              const hasCritical = events.some(e => e.severity === 'critical');
              const hasHigh = events.some(e => e.severity === 'high');
              const topEvent = events.find(e => e.severity === 'critical') || events.find(e => e.severity === 'high') || events[0];
              return (
                <div className={`mb-3 px-3 py-2 rounded-lg border text-xs ${
                  hasCritical ? 'bg-red-900/30 border-red-700/60 text-red-300' :
                  hasHigh     ? 'bg-orange-900/30 border-orange-700/60 text-orange-300' :
                                'bg-yellow-900/30 border-yellow-700/60 text-yellow-300'
                }`}>
                  <div className="flex items-center gap-1.5 font-semibold mb-1">
                    <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
                    ⚠️ {hasCritical ? 'ĐANG BỊ TẤN CÔNG' : hasHigh ? 'Phát hiện tấn công' : 'Cảnh báo bảo mật'}
                    <span className="ml-auto font-normal opacity-70">{events.length} event{events.length > 1 ? 's' : ''} / 5 phút</span>
                  </div>
                  <p className="opacity-80 truncate">{topEvent.message}</p>
                  {topEvent.source_ip && (
                    <p className="font-mono opacity-60 mt-0.5">IP: {topEvent.source_ip}</p>
                  )}
                </div>
              );
            })()}

            <div className="space-y-1.5 text-sm mb-4">
              <p className="text-slate-500">IP: <span className="font-mono text-blue-400">{server.ip_address}</span></p>
              <p className="text-slate-500">OS: <span className="text-slate-300">{server.os || 'N/A'}</span></p>
              {server.description && <p className="text-slate-600 text-xs">{server.description}</p>}
            </div>

            {/* Metrics */}
            <div className="space-y-2 mb-4">
              <div>
                <div className="flex justify-between text-xs mb-0.5">
                  <span className="flex items-center gap-1 text-slate-500"><Cpu className="w-3 h-3 text-cyan-400" /> CPU</span>
                  <span className="text-slate-400">{server.cpu_usage != null ? `${server.cpu_usage.toFixed(1)}%` : 'N/A'}</span>
                </div>
                <UsageBar value={server.cpu_usage} color="bg-cyan-500" />
              </div>
              <div>
                <div className="flex justify-between text-xs mb-0.5">
                  <span className="flex items-center gap-1 text-slate-500"><Activity className="w-3 h-3 text-violet-400" /> RAM</span>
                  <span className="text-slate-400">{server.ram_usage != null ? `${server.ram_usage.toFixed(1)}%` : 'N/A'}</span>
                </div>
                <UsageBar value={server.ram_usage} color="bg-violet-500" />
              </div>
              <div>
                <div className="flex justify-between text-xs mb-0.5">
                  <span className="flex items-center gap-1 text-slate-500"><HardDrive className="w-3 h-3 text-orange-400" /> Disk</span>
                  <span className="text-slate-400">{server.disk_usage != null ? `${server.disk_usage.toFixed(1)}%` : 'N/A'}</span>
                </div>
                <UsageBar value={server.disk_usage} color="bg-orange-500" />
              </div>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1 text-xs text-slate-600">
                {server.firewall_status === 'active'
                  ? <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  : <WifiOff className="w-3.5 h-3.5 text-red-400" />}
                <span>FW: {server.firewall_status || 'N/A'}</span>
              </div>
              <div className="flex gap-1">
                <button onClick={() => openEditModal(server)}
                  className="p-1.5 bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 rounded border border-amber-500/20 transition-colors">
                  <Edit className="w-4 h-4" />
                </button>
                <button onClick={() => openHistoryModal(server)}
                  className="p-1.5 bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 rounded border border-blue-500/20 transition-colors">
                  <LineChartIcon className="w-4 h-4" />
                </button>
                <button onClick={() => handleDeleteServer(server.id)}
                  className="p-1.5 bg-red-500/10 text-red-400 hover:bg-red-500/20 rounded border border-red-500/20 transition-colors">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
            <p className="text-slate-700 text-xs mt-3">Cập nhật: {formatDatetime(server.last_seen)}</p>
          </div>
        ))}
      </div>

      {/* Add Server Modal */}
      {showAddModal && (
        <div className={modalOverlay}>
          <div className={modalCard}>
            <div className="p-6 border-b border-slate-700/60">
              <h2 className="text-lg font-bold text-slate-100">Thêm Máy chủ Mới</h2>
            </div>
            <div className="p-6 space-y-4">
              <div><label className={labelClass}>Tên Máy chủ</label>
                <input type="text" value={newServer.name} onChange={(e) => setNewServer({ ...newServer, name: e.target.value })}
                  className={inputClass} placeholder="Web Server 01" /></div>
              <div><label className={labelClass}>Địa chỉ IP</label>
                <input type="text" value={newServer.ip_address} onChange={(e) => setNewServer({ ...newServer, ip_address: e.target.value })}
                  className={inputClass} placeholder="192.168.1.100" /></div>
              <div><label className={labelClass}>Hệ điều hành</label>
                <input type="text" value={newServer.os} onChange={(e) => setNewServer({ ...newServer, os: e.target.value })}
                  className={inputClass} placeholder="Ubuntu 22.04" /></div>
              <div><label className={labelClass}>Mô tả</label>
                <textarea value={newServer.description} onChange={(e) => setNewServer({ ...newServer, description: e.target.value })}
                  className={inputClass} rows="3" placeholder="Máy chủ web chính cho ứng dụng." /></div>
            </div>
            <div className="flex justify-end gap-3 px-6 pb-6">
              <button onClick={() => setShowAddModal(false)} className="px-4 py-2 rounded-lg text-slate-400 hover:bg-slate-800 transition-colors">Hủy</button>
              <button onClick={handleAddServer} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-medium transition-colors">Thêm</button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Server Modal */}
      {showEditModal && serverToEdit && (
        <div className={modalOverlay}>
          <div className={modalCard}>
            <div className="p-6 border-b border-slate-700/60">
              <h2 className="text-lg font-bold text-slate-100">Chỉnh sửa: {serverToEdit.name}</h2>
            </div>
            <div className="p-6 space-y-4">
              <div><label className={labelClass}>Tên Máy chủ</label>
                <input type="text" value={serverToEdit.name} onChange={(e) => setServerToEdit({ ...serverToEdit, name: e.target.value })}
                  className={inputClass} /></div>
              <div><label className={labelClass}>Địa chỉ IP</label>
                <input type="text" value={serverToEdit.ip_address} onChange={(e) => setServerToEdit({ ...serverToEdit, ip_address: e.target.value })}
                  className={inputClass} /></div>
              <div><label className={labelClass}>Hệ điều hành</label>
                <input type="text" value={serverToEdit.os} onChange={(e) => setServerToEdit({ ...serverToEdit, os: e.target.value })}
                  className={inputClass} /></div>
              <div><label className={labelClass}>Mô tả</label>
                <textarea value={serverToEdit.description} onChange={(e) => setServerToEdit({ ...serverToEdit, description: e.target.value })}
                  className={inputClass} rows="3" /></div>
            </div>
            <div className="flex justify-end gap-3 px-6 pb-6">
              <button onClick={() => { setShowEditModal(false); setServerToEdit(null) }}
                className="px-4 py-2 rounded-lg text-slate-400 hover:bg-slate-800 transition-colors">Hủy</button>
              <button onClick={handleUpdateServer} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-medium transition-colors">Cập nhật</button>
            </div>
          </div>
        </div>
      )}

      {/* History Modal */}
      {showHistoryModal && serverToEdit && (
        <div className={modalOverlay}>
          <div className="bg-slate-900 border border-slate-700/60 rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-slate-700/60 sticky top-0 bg-slate-900 z-10">
              <h2 className="text-lg font-bold text-slate-100">Lịch sử chỉ số: {serverToEdit.name}</h2>
            </div>
            <div className="p-6">
              {historyData.length === 0 ? (
                <p className="text-slate-500 text-center py-10">Không có dữ liệu lịch sử.</p>
              ) : (
                <div className="space-y-8">
                  {[
                    { title: 'Sử dụng CPU (%)', key: 'cpu_usage', color: '#22d3ee', icon: Cpu, iconColor: 'text-cyan-400' },
                    { title: 'Sử dụng RAM (%)', key: 'ram_usage', color: '#a78bfa', icon: Activity, iconColor: 'text-violet-400' },
                    { title: 'Sử dụng Đĩa (%)', key: 'disk_usage', color: '#fb923c', icon: HardDrive, iconColor: 'text-orange-400' },
                  ].map(({ title, key, color, icon: Icon, iconColor }) => (
                    <div key={key} className="bg-slate-800/40 border border-slate-700/40 rounded-xl p-4">
                      <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
                        <Icon className={`w-4 h-4 ${iconColor}`} /> {title}
                      </h3>
                      <ResponsiveContainer width="100%" height={200}>
                        <LineChart data={historyData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                          <XAxis dataKey="timestamp" tickFormatter={formatChartTime} tick={{ fontSize: 10, fill: '#64748b' }} />
                          <YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 10, fill: '#64748b' }} />
                          <Tooltip
                            formatter={(value) => `${value.toFixed(1)}%`}
                            labelFormatter={formatDatetime}
                            contentStyle={CHART_TOOLTIP_STYLE}
                          />
                          <Line type="monotone" dataKey={key} stroke={color} strokeWidth={2} dot={false} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="flex justify-end gap-3 px-6 pb-6">
              <button onClick={() => { setShowHistoryModal(false); setServerToEdit(null); setHistoryData([]) }}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-medium transition-colors">
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
