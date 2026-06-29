import React, { useEffect, useState } from 'react';
import { Server, PlusCircle, Edit, Trash2, RefreshCw, Cpu, HardDrive, ShieldCheck, WifiOff, Activity, LineChart as LineChartIcon } from 'lucide-react';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { formatDatetime, formatChartTime } from '../lib/datetime';

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

  useEffect(() => { // Tải dữ liệu lần đầu và thiết lập interval để cập nhật định kỳ
    fetchServers();
    const intervalId = setInterval(fetchServers, 10000); // Cập nhật mỗi 10 giây

    return () => clearInterval(intervalId); // Dọn dẹp interval khi component unmount
  }, []);

  const fetchServers = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await axios.get('/api/servers');
      setServers(response.data);
    } catch (err) {
      setError('Không thể tải danh sách máy chủ.');
      console.error('Error fetching servers:', err);
    } finally {
      setLoading(false);
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
      const response = await axios.get(`/api/servers/${serverId}/history?limit=50`); // Lấy 50 bản ghi gần nhất
      setHistoryData(response.data.reverse()); // Đảo ngược để hiển thị từ cũ đến mới
    } catch (err) {
      alert('Lỗi khi tải lịch sử máy chủ: ' + (err.response?.data?.detail || err.message));
    }
  };

  const openHistoryModal = (server) => {
    setServerToEdit(server); // Dùng lại serverToEdit để lưu thông tin máy chủ đang xem lịch sử
    fetchServerHistory(server.id);
    setShowHistoryModal(true);
  };

  const openEditModal = (server) => {
    setServerToEdit({ ...server }); // Tạo bản sao để tránh sửa trực tiếp state
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

  const getStatusColor = (status) => {
    switch (status) {
      case 'online': return 'text-green-400';
      case 'warning': return 'text-yellow-400';
      case 'offline': return 'text-red-400';
      default: return 'text-gray-400';
    }
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Server className="w-8 h-8 text-blue-500" />
          <h1 className="text-2xl font-bold text-gray-900">Quản lý Máy chủ</h1>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-medium transition-colors"
        >
          <PlusCircle className="w-5 h-5" /> Thêm Máy chủ
        </button>
      </div>

      {loading && <p className="text-gray-400">Đang tải danh sách máy chủ...</p>}
      {error && <p className="text-red-500">{error}</p>}

      {!loading && !error && servers.length === 0 && (
        <p className="text-gray-400">Chưa có máy chủ nào được thêm.</p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {servers.map((server) => (
          <div key={server.id} className="bg-white p-6 rounded-xl border border-gray-200 shadow-lg">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-gray-800">{server.name}</h2>
              <span className={`px-3 py-1 rounded-full text-xs font-semibold ${getStatusColor(server.status)} bg-opacity-20`}>
                {server.status.toUpperCase()}
              </span>
            </div>
            <p className="text-gray-600 text-sm mb-2">IP: <span className="font-mono text-blue-600">{server.ip_address}</span></p>
            <p className="text-gray-600 text-sm mb-2">OS: {server.os || 'N/A'}</p>
            <p className="text-gray-600 text-sm mb-4">{server.description || 'Không có mô tả.'}</p>

            <div className="grid grid-cols-2 gap-3 text-sm text-gray-700 mb-4">
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-cyan-400" /> CPU: {server.cpu_usage ? `${server.cpu_usage.toFixed(1)}%` : 'N/A'}
              </div>
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-purple-400" /> RAM: {server.ram_usage ? `${server.ram_usage.toFixed(1)}%` : 'N/A'}
              </div>
              <div className="flex items-center gap-2">
                <HardDrive className="w-4 h-4 text-orange-400" /> Disk: {server.disk_usage ? `${server.disk_usage.toFixed(1)}%` : 'N/A'}
              </div>
              <div className="flex items-center gap-2">
                {server.firewall_status === 'active' ? <ShieldCheck className="w-4 h-4 text-green-400" /> : <WifiOff className="w-4 h-4 text-red-400" />}
                FW: {server.firewall_status || 'N/A'}
              </div>
            </div>
            <p className="text-gray-500 text-xs">Cập nhật cuối: {formatDatetime(server.last_seen)}</p>

            <div className="flex justify-end gap-2 mt-4">
              <button onClick={() => openEditModal(server)} className="text-yellow-600 hover:text-yellow-700 p-1 rounded-md">
                <Edit className="w-5 h-5" />
              </button>
              <button onClick={() => openHistoryModal(server)} className="text-blue-600 hover:text-blue-700 p-1 rounded-md">
                <LineChartIcon className="w-5 h-5" />
              </button>
              <button onClick={() => handleDeleteServer(server.id)} className="text-red-600 hover:text-red-700 p-1 rounded-md">
                <Trash2 className="w-5 h-5" />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Add Server Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white p-8 rounded-xl shadow-2xl border border-gray-200 w-full max-w-md">
            <h2 className="text-xl font-bold text-gray-800 mb-6">Thêm Máy chủ Mới</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">Tên Máy chủ</label>
                <input
                  type="text"
                  value={newServer.name}
                  onChange={(e) => setNewServer({ ...newServer, name: e.target.value })}
                  className="w-full bg-white border border-gray-300 rounded-lg px-4 py-2 text-gray-700 focus:ring-2 focus:ring-blue-500 outline-none"
                  placeholder="Web Server 01"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">Địa chỉ IP</label>
                <input
                  type="text"
                  value={newServer.ip_address}
                  onChange={(e) => setNewServer({ ...newServer, ip_address: e.target.value })}
                  className="w-full bg-white border border-gray-300 rounded-lg px-4 py-2 text-gray-700 focus:ring-2 focus:ring-blue-500 outline-none"
                  placeholder="192.168.1.100"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">Hệ điều hành</label>
                <input
                  type="text"
                  value={newServer.os}
                  onChange={(e) => setNewServer({ ...newServer, os: e.target.value })}
                  className="w-full bg-white border border-gray-300 rounded-lg px-4 py-2 text-gray-700 focus:ring-2 focus:ring-blue-500 outline-none"
                  placeholder="Ubuntu 22.04"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">Mô tả</label>
                <textarea
                  value={newServer.description}
                  onChange={(e) => setNewServer({ ...newServer, description: e.target.value })}
                  className="w-full bg-white border border-gray-300 rounded-lg px-4 py-2 text-gray-700 focus:ring-2 focus:ring-blue-500 outline-none"
                  rows="3"
                  placeholder="Máy chủ web chính cho ứng dụng."
                ></textarea>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowAddModal(false)} className="px-4 py-2 rounded-lg text-gray-600 hover:bg-gray-100 transition-colors">Hủy</button>
              <button onClick={handleAddServer} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-medium transition-colors">Thêm</button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Server Modal */}
      {showEditModal && serverToEdit && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white p-8 rounded-xl shadow-2xl border border-gray-200 w-full max-w-md">
            <h2 className="text-xl font-bold text-gray-800 mb-6">Chỉnh sửa Máy chủ: {serverToEdit.name}</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">Tên Máy chủ</label>
                <input
                  type="text"
                  value={serverToEdit.name}
                  onChange={(e) => setServerToEdit({ ...serverToEdit, name: e.target.value })}
                  className="w-full bg-white border border-gray-300 rounded-lg px-4 py-2 text-gray-700 focus:ring-2 focus:ring-blue-500 outline-none"
                  placeholder="Web Server 01"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">Địa chỉ IP</label>
                <input
                  type="text"
                  value={serverToEdit.ip_address}
                  onChange={(e) => setServerToEdit({ ...serverToEdit, ip_address: e.target.value })}
                  className="w-full bg-white border border-gray-300 rounded-lg px-4 py-2 text-gray-700 focus:ring-2 focus:ring-blue-500 outline-none"
                  placeholder="192.168.1.100"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">Hệ điều hành</label>
                <input
                  type="text"
                  value={serverToEdit.os}
                  onChange={(e) => setServerToEdit({ ...serverToEdit, os: e.target.value })}
                  className="w-full bg-white border border-gray-300 rounded-lg px-4 py-2 text-gray-700 focus:ring-2 focus:ring-blue-500 outline-none"
                  placeholder="Ubuntu 22.04"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">Mô tả</label>
                <textarea
                  value={serverToEdit.description}
                  onChange={(e) => setServerToEdit({ ...serverToEdit, description: e.target.value })}
                  className="w-full bg-white border border-gray-300 rounded-lg px-4 py-2 text-gray-700 focus:ring-2 focus:ring-blue-500 outline-none"
                  rows="3"
                  placeholder="Máy chủ web chính cho ứng dụng."
                ></textarea>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => {
                  setShowEditModal(false);
                  setServerToEdit(null);
                }}
                className="px-4 py-2 rounded-lg text-gray-600 hover:bg-gray-100 transition-colors"
              >
                Hủy
              </button>
              <button
                onClick={handleUpdateServer}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-medium transition-colors"
              >
                Cập nhật
              </button>
            </div>
          </div>
        </div>
      )}

      {/* History Modal */}
      {showHistoryModal && serverToEdit && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white p-8 rounded-xl shadow-2xl border border-gray-200 w-full max-w-4xl max-h-[90vh] overflow-y-auto">
            <h2 className="text-xl font-bold text-gray-800 mb-6">Lịch sử chỉ số: {serverToEdit.name}</h2>
            
            {historyData.length === 0 ? (
              <p className="text-gray-400 text-center py-10">Không có dữ liệu lịch sử.</p>
            ) : (
              <div className="space-y-8">
                {/* CPU Usage Chart */}
                <div>
                  <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <Cpu className="w-5 h-5 text-cyan-400" /> Sử dụng CPU (%)
                  </h3>
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={historyData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#4b5563" />
                      <XAxis dataKey="timestamp" tickFormatter={formatChartTime} stroke="#9ca3af" />
                      <YAxis domain={[0, 100]} unit="%" stroke="#9ca3af" />
                      <Tooltip formatter={(value) => `${value.toFixed(1)}%`} labelFormatter={formatDatetime} />
                      <Line type="monotone" dataKey="cpu_usage" stroke="#22d3ee" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                {/* RAM Usage Chart */}
                <div>
                  <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <Activity className="w-5 h-5 text-purple-400" /> Sử dụng RAM (%)
                  </h3>
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={historyData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#4b5563" />
                      <XAxis dataKey="timestamp" tickFormatter={formatChartTime} stroke="#9ca3af" />
                      <YAxis domain={[0, 100]} unit="%" stroke="#9ca3af" />
                      <Tooltip formatter={(value) => `${value.toFixed(1)}%`} labelFormatter={formatDatetime} />
                      <Line type="monotone" dataKey="ram_usage" stroke="#a78bfa" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                {/* Disk Usage Chart */}
                <div>
                  <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <HardDrive className="w-5 h-5 text-orange-400" /> Sử dụng Đĩa (%)
                  </h3>
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={historyData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#4b5563" />
                      <XAxis dataKey="timestamp" tickFormatter={formatChartTime} stroke="#9ca3af" />
                      <YAxis domain={[0, 100]} unit="%" stroke="#9ca3af" />
                      <Tooltip formatter={(value) => `${value.toFixed(1)}%`} labelFormatter={formatDatetime} />
                      <Line type="monotone" dataKey="disk_usage" stroke="#fb923c" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => {
                  setShowHistoryModal(false);
                  setServerToEdit(null);
                  setHistoryData([]);
                }}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-medium transition-colors"
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
