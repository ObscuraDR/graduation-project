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
      <div className="p-6 text-center text-red-500">
        <AlertCircle className="w-12 h-12 mx-auto mb-3" />
        <p className="text-xl font-semibold">Truy cập bị từ chối</p>
        <p className="text-gray-400">Bạn không có quyền xem trang này.</p>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Users className="w-8 h-8 text-blue-500" />
          <h1 className="text-2xl font-bold text-white">Quản lý Người dùng</h1>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-medium transition-colors"
        >
          <PlusCircle className="w-5 h-5" /> Thêm Người dùng
        </button>
      </div>

      {message.text && (
        <div className={`mb-4 p-3 rounded-lg flex items-center gap-2 ${
          message.type === 'success' ? 'bg-green-500/10 text-green-400 border border-green-500/30' : 'bg-red-500/10 text-red-400 border border-red-500/30'
        }`}>
          {message.type === 'success' ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
          {message.text}
        </div>
      )}

      {loading && <p className="text-gray-400">Đang tải danh sách người dùng...</p>}
      {error && <p className="text-red-500">{error}</p>}

      {!loading && !error && users.length === 0 && (
        <p className="text-gray-400">Chưa có người dùng nào.</p>
      )}

      {!loading && !error && users.length > 0 && (
        <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
          <table className="w-full text-left text-gray-300">
            <thead className="bg-gray-900/50 text-gray-400 text-xs uppercase">
              <tr>
                <th className="px-6 py-4">ID</th>
                <th className="px-6 py-4">Tên đăng nhập</th>
                <th className="px-6 py-4">Email</th>
                <th className="px-6 py-4">Vai trò</th>
                <th className="px-6 py-4">Ngày tạo</th>
                <th className="px-6 py-4 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {users.map((user) => (
                <tr key={user.id} className="hover:bg-gray-750">
                  <td className="px-6 py-4 text-sm">{user.id}</td>
                  <td className="px-6 py-4 font-medium text-white">{user.username}</td>
                  <td className="px-6 py-4 text-sm">{user.email || 'N/A'}</td>
                  <td className="px-6 py-4">
                    <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold capitalize ${
                      user.role === 'admin' ? 'bg-red-600/20 text-red-400' :
                      user.role === 'security_analyst' ? 'bg-yellow-600/20 text-yellow-400' :
                      'bg-blue-600/20 text-blue-400'
                    }`}>
                      {user.role}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-xs">{formatDatetime(user.created_at)}</td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => openEditModal(user)}
                        className="text-yellow-500 hover:text-yellow-400 p-1 rounded-md"
                        title="Chỉnh sửa vai trò"
                      >
                        <Edit className="w-5 h-5" />
                      </button>
                      <button
                        onClick={() => handleResetPassword(user.id, user.username)}
                        className="text-blue-500 hover:text-blue-400 p-1 rounded-md"
                        title="Đặt lại mật khẩu"
                        disabled={user.id === currentUser.id} // Không cho phép reset mật khẩu của chính mình
                      >
                        <KeyRound className="w-5 h-5" />
                      </button>
                      <button
                        onClick={() => handleDeleteUser(user.id, user.username)}
                        className="text-red-500 hover:text-red-400 p-1 rounded-md"
                        title="Xóa người dùng"
                        disabled={user.id === currentUser.id} // Không cho phép xóa chính mình
                      >
                        <Trash2 className="w-5 h-5" />
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
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50">
          <div className="bg-gray-800 p-8 rounded-xl shadow-2xl border border-gray-700 w-full max-w-md">
            <h2 className="text-xl font-bold text-white mb-6">Thêm Người dùng Mới</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Tên đăng nhập</label>
                <input
                  type="text"
                  value={newUserData.username}
                  onChange={(e) => setNewUserData({ ...newUserData, username: e.target.value })}
                  className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-white focus:ring-2 focus:ring-blue-500 outline-none"
                  placeholder="username"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Email</label>
                <input
                  type="email"
                  value={newUserData.email}
                  onChange={(e) => setNewUserData({ ...newUserData, email: e.target.value })}
                  className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-white focus:ring-2 focus:ring-blue-500 outline-none"
                  placeholder="user@example.com"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Mật khẩu</label>
                <input
                  type="password"
                  value={newUserData.password}
                  onChange={(e) => setNewUserData({ ...newUserData, password: e.target.value })}
                  className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-white focus:ring-2 focus:ring-blue-500 outline-none"
                  placeholder="••••••••"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Vai trò</label>
                <select
                  value={newUserData.role}
                  onChange={(e) => setNewUserData({ ...newUserData, role: e.target.value })}
                  className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-white focus:ring-2 focus:ring-blue-500 outline-none"
                >
                  {ROLES.map(role => <option key={role} value={role}>{role.replace('_', ' ').toUpperCase()}</option>)}
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowAddModal(false)} className="px-4 py-2 rounded-lg text-gray-300 hover:bg-gray-700 transition-colors">Hủy</button>
              <button onClick={handleAddUser} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-medium transition-colors">Thêm</button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Role Modal */}
      {showEditModal && currentUserToEdit && (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50">
          <div className="bg-gray-800 p-8 rounded-xl shadow-2xl border border-gray-700 w-full max-w-md">
            <h2 className="text-xl font-bold text-white mb-6">Chỉnh sửa Vai trò: {currentUserToEdit.username}</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Vai trò</label>
                <select
                  value={editRoleData.role}
                  onChange={(e) => setEditRoleData({ ...editRoleData, role: e.target.value })}
                  className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-white focus:ring-2 focus:ring-blue-500 outline-none"
                >
                  {ROLES.map(role => <option key={role} value={role}>{role.replace('_', ' ').toUpperCase()}</option>)}
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowEditModal(false)} className="px-4 py-2 rounded-lg text-gray-300 hover:bg-gray-700 transition-colors">Hủy</button>
              <button onClick={handleEditRole} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-medium transition-colors">Cập nhật</button>
            </div>
          </div>
        </div>
      )}

      {/* Reset Password Result Modal */}
      {showResetPasswordModal && (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50">
          <div className="bg-gray-800 p-8 rounded-xl shadow-2xl border border-gray-700 w-full max-w-md text-center">
            <CheckCircle2 className="w-16 h-16 text-green-500 mx-auto mb-4" />
            <h2 className="text-xl font-bold text-white mb-3">Mật khẩu đã được đặt lại!</h2>
            <p className="text-gray-300 mb-4">
              Mật khẩu mới cho người dùng <span className="font-semibold text-blue-400">{resetPasswordResult.username}</span> là:
            </p>
            <div className="bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 mb-6">
              <p className="font-mono text-lg text-green-400 break-all">{resetPasswordResult.newPassword}</p>
            </div>
            <p className="text-sm text-red-400 mb-6">
              Vui lòng sao chép mật khẩu này ngay lập tức. Nó sẽ không được hiển thị lại.
            </p>
            <button onClick={() => setShowResetPasswordModal(false)} className="px-6 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-medium transition-colors">Đóng</button>
          </div>
        </div>
      )}

    </div>
  );
}