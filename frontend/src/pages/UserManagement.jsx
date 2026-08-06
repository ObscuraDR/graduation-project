import React, { useEffect, useState } from 'react';
import api from '../lib/api';
import { Users, PlusCircle, Edit, Trash2, UserCheck, Loader2, AlertCircle, CheckCircle2, KeyRound } from 'lucide-react';
import { hasRole, getUser } from '../lib/auth';
import { formatDatetime } from '../lib/datetime';

const ROLES = ['admin', 'security_analyst', 'operator'];

export default function UserManagement() {
  const currentUser = getUser();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [currentUserToEdit, setCurrentUserToEdit] = useState(null);
  const [showResetPasswordModal, setShowResetPasswordModal] = useState(false);
  const [resetPasswordResult, setResetPasswordResult] = useState({ username: '', newPassword: '' });
  const [newUserData, setNewUserData] = useState({ username: '', email: '', password: '', role: 'operator' });
  const [editRoleData, setEditRoleData] = useState({ role: '' });
  const [message, setMessage] = useState({ type: '', text: '' });

  const flashMessage = (type, text) => {
    setMessage({ type, text });
    setTimeout(() => setMessage({ type: '', text: '' }), 3000);
  };

  useEffect(() => {
    if (!hasRole(['admin'])) {
      setError('Bạn không có quyền truy cập trang này.');
      setLoading(false);
      return;
    }
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await api.get('/auth/users');
      setUsers(response.data);
    } catch (err) {
      setError('Không thể tải danh sách người dùng: ' + (err.response?.data?.detail || err.message));
      console.error('Error fetching users:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddUser = async () => {
    try {
      await api.post('/auth/users', newUserData);
      flashMessage('success', `Người dùng ${newUserData.username} đã được thêm.`);
      setShowAddModal(false);
      setNewUserData({ username: '', email: '', password: '', role: 'operator' });
      fetchUsers();
    } catch (err) {
      flashMessage('error', 'Lỗi khi thêm người dùng: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleEditRole = async () => {
    if (!currentUserToEdit) return;
    try {
      await api.put(`/auth/users/${currentUserToEdit.id}/role`, editRoleData);
      flashMessage('success', `Vai trò của ${currentUserToEdit.username} đã được cập nhật.`);
      setShowEditModal(false);
      setCurrentUserToEdit(null);
      fetchUsers();
    } catch (err) {
      flashMessage('error', 'Lỗi khi cập nhật vai trò: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleDeleteUser = async (userId, username) => {
    if (window.confirm(`Bạn có chắc muốn xóa người dùng ${username} không?`)) {
      try {
        await api.delete(`/auth/users/${userId}`);
        flashMessage('success', `Người dùng ${username} đã bị xóa.`);
        fetchUsers();
      } catch (err) {
        flashMessage('error', 'Lỗi khi xóa người dùng: ' + (err.response?.data?.detail || err.message));
      }
    }
  };

  const handleResetPassword = async (userId, username) => {
    if (window.confirm(`Bạn có chắc muốn đặt lại mật khẩu cho người dùng ${username}?`)) {
      try {
        const response = await api.post(`/auth/users/${userId}/reset-password`, {});
        setResetPasswordResult({ username, newPassword: response.data.new_password });
        setShowResetPasswordModal(true);
        flashMessage('success', `Mật khẩu cho ${username} đã được đặt lại.`);
      } catch (err) {
        flashMessage('error', 'Lỗi khi đặt lại mật khẩu: ' + (err.response?.data?.detail || err.message));
      }
    }
  };

  const openEditModal = (user) => {
    setCurrentUserToEdit(user);
    setEditRoleData({ role: user.role });
    setShowEditModal(true);
  };

  if (!hasRole(['admin'])) {
    return (
      <div className="p-6 text-center text-red-400">
        <AlertCircle className="w-12 h-12 mx-auto mb-3" />
        <p className="text-xl font-semibold">Truy cập bị từ chối</p>
        <p className="text-slate-400">Bạn không có quyền xem trang này.</p>
      </div>
    );
  }

  const inputClass = "w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-slate-200 focus:ring-2 focus:ring-blue-500 outline-none";

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-blue-500/10 border border-blue-500/20">
            <Users className="w-6 h-6 text-blue-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-100">Quản lý Người dùng</h1>
            <p className="text-sm text-slate-500">Tài khoản và phân quyền hệ thống</p>
          </div>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-medium transition-colors shadow-lg shadow-blue-500/20"
        >
          <PlusCircle className="w-5 h-5" /> Thêm Người dùng
        </button>
      </div>

      {message.text && (
        <div className={`p-3 rounded-lg flex items-center gap-2 border ${
          message.type === 'success' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' : 'bg-red-500/10 text-red-400 border-red-500/30'
        }`}>
          {message.type === 'success' ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
          {message.text}
        </div>
      )}

      {loading && <p className="text-slate-400">Đang tải danh sách người dùng...</p>}
      {error && <p className="text-red-400">{error}</p>}

      {!loading && !error && users.length === 0 && (
        <p className="text-slate-400">Chưa có người dùng nào.</p>
      )}

      {!loading && !error && users.length > 0 && (
        <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 overflow-hidden">
          <table className="w-full text-left text-slate-300 text-sm">
            <thead className="bg-slate-800/80 text-slate-400 text-xs uppercase border-b border-slate-700/60">
              <tr>
                <th className="px-6 py-4">ID</th>
                <th className="px-6 py-4">Tên đăng nhập</th>
                <th className="px-6 py-4">Email</th>
                <th className="px-6 py-4">Vai trò</th>
                <th className="px-6 py-4">Ngày tạo</th>
                <th className="px-6 py-4 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {users.map((user) => (
                <tr key={user.id} className="hover:bg-slate-800/40 transition-colors">
                  <td className="px-6 py-4 text-sm text-slate-400">{user.id}</td>
                  <td className="px-6 py-4 font-medium text-slate-200">{user.username}</td>
                  <td className="px-6 py-4 text-sm text-slate-400">{user.email || 'N/A'}</td>
                  <td className="px-6 py-4">
                    <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold capitalize border ${
                      user.role === 'admin' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                      user.role === 'security_analyst' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' :
                      'bg-blue-500/10 text-blue-400 border-blue-500/20'
                    }`}>
                      {user.role}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-xs text-slate-400">{formatDatetime(user.created_at)}</td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => openEditModal(user)}
                        className="text-amber-400 hover:text-amber-300 p-1.5 bg-amber-500/10 rounded-lg border border-amber-500/20 transition-colors"
                        title="Chỉnh sửa vai trò"
                      >
                        <Edit className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleResetPassword(user.id, user.username)}
                        className="text-blue-400 hover:text-blue-300 p-1.5 bg-blue-500/10 rounded-lg border border-blue-500/20 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                        title="Đặt lại mật khẩu"
                        disabled={user.id === currentUser?.id}
                      >
                        <KeyRound className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDeleteUser(user.id, user.username)}
                        className="text-red-400 hover:text-red-300 p-1.5 bg-red-500/10 rounded-lg border border-red-500/20 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                        title="Xóa người dùng"
                        disabled={user.id === currentUser?.id}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Add User Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-slate-900 border border-slate-800 p-8 rounded-2xl shadow-2xl w-full max-w-md">
            <h2 className="text-xl font-bold text-slate-100 mb-6">Thêm Người dùng Mới</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-1">Tên đăng nhập</label>
                <input
                  type="text"
                  value={newUserData.username}
                  onChange={(e) => setNewUserData({ ...newUserData, username: e.target.value })}
                  className={inputClass}
                  placeholder="username"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-1">Email</label>
                <input
                  type="email"
                  value={newUserData.email}
                  onChange={(e) => setNewUserData({ ...newUserData, email: e.target.value })}
                  className={inputClass}
                  placeholder="user@example.com"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-1">Mật khẩu</label>
                <input
                  type="password"
                  value={newUserData.password}
                  onChange={(e) => setNewUserData({ ...newUserData, password: e.target.value })}
                  className={inputClass}
                  placeholder="••••••••"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-1">Vai trò</label>
                <select
                  value={newUserData.role}
                  onChange={(e) => setNewUserData({ ...newUserData, role: e.target.value })}
                  className={inputClass}
                >
                  {ROLES.map(role => <option key={role} value={role}>{role.replace('_', ' ').toUpperCase()}</option>)}
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowAddModal(false)} className="px-4 py-2 rounded-lg text-slate-400 hover:bg-slate-800 transition-colors">Hủy</button>
              <button onClick={handleAddUser} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-medium transition-colors">Thêm</button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Role Modal */}
      {showEditModal && currentUserToEdit && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-slate-900 border border-slate-800 p-8 rounded-2xl shadow-2xl w-full max-w-md">
            <h2 className="text-xl font-bold text-slate-100 mb-6">Chỉnh sửa Vai trò: {currentUserToEdit.username}</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-1">Vai trò</label>
                <select
                  value={editRoleData.role}
                  onChange={(e) => setEditRoleData({ ...editRoleData, role: e.target.value })}
                  className={inputClass}
                >
                  {ROLES.map(role => <option key={role} value={role}>{role.replace('_', ' ').toUpperCase()}</option>)}
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowEditModal(false)} className="px-4 py-2 rounded-lg text-slate-400 hover:bg-slate-800 transition-colors">Hủy</button>
              <button onClick={handleEditRole} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-medium transition-colors">Cập nhật</button>
            </div>
          </div>
        </div>
      )}

      {/* Reset Password Result Modal */}
      {showResetPasswordModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-slate-900 border border-slate-800 p-8 rounded-2xl shadow-2xl w-full max-w-md text-center">
            <CheckCircle2 className="w-16 h-16 text-emerald-400 mx-auto mb-4" />
            <h2 className="text-xl font-bold text-slate-100 mb-3">Mật khẩu đã được đặt lại!</h2>
            <p className="text-slate-400 mb-4">
              Mật khẩu mới cho người dùng <span className="font-semibold text-blue-400">{resetPasswordResult.username}</span> là:
            </p>
            <div className="bg-slate-800/80 border border-slate-700/60 rounded-xl px-4 py-3 mb-6">
              <p className="font-mono text-lg text-emerald-400 break-all">{resetPasswordResult.newPassword}</p>
            </div>
            <p className="text-xs text-amber-400 mb-6">
              Vui lòng sao chép mật khẩu này ngay lập tức. Nó sẽ không được hiển thị lại.
            </p>
            <button onClick={() => setShowResetPasswordModal(false)} className="px-6 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-medium transition-colors">Đóng</button>
          </div>
        </div>
      )}

    </div>
  );
}