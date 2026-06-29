import React, { useEffect, useState } from 'react';
import api from '../lib/api';
import { Users, PlusCircle, Edit, Trash2, UserCheck, Loader2, AlertCircle, CheckCircle2, KeyRound, History, Shield } from 'lucide-react';
import { hasRole, getUser } from '../lib/auth';
import { formatDatetime } from '../lib/datetime';
import { fetchAuditLogs } from '../lib/api';
import Pagination from '../components/Pagination';

const ROLES = ['admin', 'security_analyst', 'operator'];

const ACTION_LABELS = {
  login: 'Đăng nhập',
  logout: 'Đăng xuất',
  change_password: 'Đổi mật khẩu',
  create_server: 'Thêm server',
  delete_server: 'Xóa server',
};

const TABS = [
  { id: 'users', label: 'Quản lý Người dùng', icon: Users },
  { id: 'audit', label: 'Audit Log', icon: History },
];

export default function UserManagementAndAudit() {
  const [activeTab, setActiveTab] = useState('users');
  const currentUser = getUser();
  
  // User Management State
  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(true);
  const [usersError, setUsersError] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [currentUserToEdit, setCurrentUserToEdit] = useState(null);
  const [showResetPasswordModal, setShowResetPasswordModal] = useState(false);
  const [resetPasswordResult, setResetPasswordResult] = useState({ username: '', newPassword: '' });
  const [newUserData, setNewUserData] = useState({ username: '', email: '', password: '', role: 'operator' });
  const [editRoleData, setEditRoleData] = useState({ role: '' });
  const [userMessage, setUserMessage] = useState({ type: '', text: '' });

  // Audit Logs State
  const [logs, setLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [total, setTotal] = useState(0);

  const flashUserMessage = (type, text) => {
    setUserMessage({ type, text });
    setTimeout(() => setUserMessage({ type: '', text: '' }), 3000);
  };

  // User Management Effects
  useEffect(() => {
    if (activeTab === 'users') {
      fetchUsers();
    }
  }, [activeTab]);

  // Audit Logs Effects
  useEffect(() => {
    if (activeTab === 'audit') {
      setLogsLoading(true);
      const params = { limit: pageSize, skip: (currentPage - 1) * pageSize };
      if (actionFilter) params.action = actionFilter;
      fetchAuditLogs(params)
        .then((data) => {
          setLogs(data.items || data);
          setTotal(data.total || data.length || 0);
        })
        .catch(console.error)
        .finally(() => setLogsLoading(false));
    }
  }, [activeTab, currentPage, pageSize]);

  useEffect(() => {
    if (activeTab === 'audit') {
      setCurrentPage(1);
      setLogsLoading(true);
      const params = { limit: pageSize, skip: 0 };
      if (actionFilter) params.action = actionFilter;
      fetchAuditLogs(params)
        .then((data) => {
          setLogs(data.items || data);
          setTotal(data.total || data.length || 0);
        })
        .catch(console.error)
        .finally(() => setLogsLoading(false));
    }
  }, [actionFilter, activeTab]);

  // User Management Functions
  const fetchUsers = async () => {
    setUsersLoading(true);
    setUsersError('');
    try {
      const response = await api.get('/auth/users');
      setUsers(response.data);
    } catch (err) {
      setUsersError('Không thể tải danh sách người dùng: ' + (err.response?.data?.detail || err.message));
      console.error('Error fetching users:', err);
    } finally {
      setUsersLoading(false);
    }
  };

  const handleAddUser = async () => {
    try {
      await api.post('/auth/users', newUserData);
      flashUserMessage('success', `Người dùng ${newUserData.username} đã được thêm.`);
      setShowAddModal(false);
      setNewUserData({ username: '', email: '', password: '', role: 'operator' });
      fetchUsers();
    } catch (err) {
      flashUserMessage('error', 'Lỗi khi thêm người dùng: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleEditRole = async () => {
    if (!currentUserToEdit) return;
    try {
      await api.put(`/auth/users/${currentUserToEdit.id}/role`, editRoleData);
      flashUserMessage('success', `Vai trò của ${currentUserToEdit.username} đã được cập nhật.`);
      setShowEditModal(false);
      setCurrentUserToEdit(null);
      fetchUsers();
    } catch (err) {
      flashUserMessage('error', 'Lỗi khi cập nhật vai trò: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleDeleteUser = async (userId, username) => {
    if (window.confirm(`Bạn có chắc muốn xóa người dùng ${username} không?`)) {
      try {
        await api.delete(`/auth/users/${userId}`);
        flashUserMessage('success', `Người dùng ${username} đã bị xóa.`);
        fetchUsers();
      } catch (err) {
        flashUserMessage('error', 'Lỗi khi xóa người dùng: ' + (err.response?.data?.detail || err.message));
      }
    }
  };

  const handleResetPassword = async (userId, username) => {
    if (window.confirm(`Bạn có chắc muốn đặt lại mật khẩu cho người dùng ${username}?`)) {
      try {
        const response = await api.post(`/auth/users/${userId}/reset-password`, {});
        setResetPasswordResult({ username, newPassword: response.data.new_password });
        setShowResetPasswordModal(true);
        flashUserMessage('success', `Mật khẩu cho ${username} đã được đặt lại.`);
      } catch (err) {
        flashUserMessage('error', 'Lỗi khi đặt lại mật khẩu: ' + (err.response?.data?.detail || err.message));
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
    <div className="p-6 space-y-6">
      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-200 mb-6">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors ${
              activeTab === id
                ? 'border-blue-500 text-blue-600 bg-blue-50'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-50'
            }`}
          >
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      {/* User Management Tab */}
      {activeTab === 'users' && (
        <>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Users className="w-8 h-8 text-blue-500" />
              <h1 className="text-2xl font-bold text-gray-900">Quản lý Người dùng</h1>
            </div>
            <button
              onClick={() => setShowAddModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-medium transition-colors"
            >
              <PlusCircle className="w-5 h-5" /> Thêm Người dùng
            </button>
          </div>

          {userMessage.text && (
            <div className={`p-3 rounded-lg flex items-center gap-2 ${
              userMessage.type === 'success' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'
            }`}>
              {userMessage.type === 'success' ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
              {userMessage.text}
            </div>
          )}

          {usersLoading && <p className="text-gray-400">Đang tải danh sách người dùng...</p>}
          {usersError && <p className="text-red-500">{usersError}</p>}

          {!usersLoading && !usersError && users.length === 0 && (
            <p className="text-gray-400">Chưa có người dùng nào.</p>
          )}

          {!usersLoading && !usersError && users.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden flex-1 flex flex-col" style={{ maxHeight: 'calc(100vh - 300px)' }}>
              <div className="overflow-auto flex-1">
                <table className="w-full text-left text-gray-700">
                  <thead className="bg-gray-50 text-gray-600 text-xs uppercase sticky top-0">
                    <tr>
                      <th className="px-6 py-4">ID</th>
                      <th className="px-6 py-4">Tên đăng nhập</th>
                      <th className="px-6 py-4">Email</th>
                      <th className="px-6 py-4">Vai trò</th>
                      <th className="px-6 py-4">Ngày tạo</th>
                      <th className="px-6 py-4 text-right">Thao tác</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                  {users.map((user) => (
                    <tr key={user.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 text-sm text-gray-600">{user.id}</td>
                      <td className="px-6 py-4 font-medium text-gray-800">{user.username}</td>
                      <td className="px-6 py-4 text-sm text-gray-700">{user.email || 'N/A'}</td>
                      <td className="px-6 py-4">
                        <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold capitalize ${
                          user.role === 'admin' ? 'bg-red-100 text-red-700' :
                          user.role === 'security_analyst' ? 'bg-yellow-100 text-yellow-700' :
                          'bg-blue-100 text-blue-700'
                        }`}>
                          {user.role}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-xs text-gray-600">{formatDatetime(user.created_at)}</td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={() => openEditModal(user)}
                            className="text-yellow-600 hover:text-yellow-700 p-1 rounded-md"
                            title="Chỉnh sửa vai trò"
                          >
                            <Edit className="w-5 h-5" />
                          </button>
                          <button
                            onClick={() => handleResetPassword(user.id, user.username)}
                            className="text-blue-600 hover:text-blue-700 p-1 rounded-md"
                            title="Đặt lại mật khẩu"
                            disabled={user.id === currentUser.id}
                          >
                            <KeyRound className="w-5 h-5" />
                          </button>
                          <button
                            onClick={() => handleDeleteUser(user.id, user.username)}
                            className="text-red-600 hover:text-red-700 p-1 rounded-md"
                            title="Xóa người dùng"
                            disabled={user.id === currentUser.id}
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
            </div>
          )}

          {/* Add User Modal */}
          {showAddModal && (
            <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
              <div className="bg-white p-8 rounded-xl shadow-2xl border border-gray-200 w-full max-w-md">
                <h2 className="text-xl font-bold text-gray-800 mb-6">Thêm Người dùng Mới</h2>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-600 mb-1">Tên đăng nhập</label>
                    <input
                      type="text"
                      value={newUserData.username}
                      onChange={(e) => setNewUserData({ ...newUserData, username: e.target.value })}
                      className="w-full bg-white border border-gray-300 rounded-lg px-4 py-2 text-gray-700 focus:ring-2 focus:ring-blue-500 outline-none"
                      placeholder="username"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-600 mb-1">Email</label>
                    <input
                      type="email"
                      value={newUserData.email}
                      onChange={(e) => setNewUserData({ ...newUserData, email: e.target.value })}
                      className="w-full bg-white border border-gray-300 rounded-lg px-4 py-2 text-gray-700 focus:ring-2 focus:ring-blue-500 outline-none"
                      placeholder="user@example.com"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-600 mb-1">Mật khẩu</label>
                    <input
                      type="password"
                      value={newUserData.password}
                      onChange={(e) => setNewUserData({ ...newUserData, password: e.target.value })}
                      className="w-full bg-white border border-gray-300 rounded-lg px-4 py-2 text-gray-700 focus:ring-2 focus:ring-blue-500 outline-none"
                      placeholder="••••••••"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-600 mb-1">Vai trò</label>
                    <select
                      value={newUserData.role}
                      onChange={(e) => setNewUserData({ ...newUserData, role: e.target.value })}
                      className="w-full bg-white border border-gray-300 rounded-lg px-4 py-2 text-gray-700 focus:ring-2 focus:ring-blue-500 outline-none"
                    >
                      {ROLES.map(role => <option key={role} value={role}>{role.replace('_', ' ').toUpperCase()}</option>)}
                    </select>
                  </div>
                </div>
                <div className="flex justify-end gap-3 mt-6">
                  <button onClick={() => setShowAddModal(false)} className="px-4 py-2 rounded-lg text-gray-600 hover:bg-gray-100 transition-colors">Hủy</button>
                  <button onClick={handleAddUser} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-medium transition-colors">Thêm</button>
                </div>
              </div>
            </div>
          )}

          {/* Edit Role Modal */}
          {showEditModal && currentUserToEdit && (
            <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
              <div className="bg-white p-8 rounded-xl shadow-2xl border border-gray-200 w-full max-w-md">
                <h2 className="text-xl font-bold text-gray-800 mb-6">Chỉnh sửa Vai trò: {currentUserToEdit.username}</h2>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-600 mb-1">Vai trò</label>
                    <select
                      value={editRoleData.role}
                      onChange={(e) => setEditRoleData({ ...editRoleData, role: e.target.value })}
                      className="w-full bg-white border border-gray-300 rounded-lg px-4 py-2 text-gray-700 focus:ring-2 focus:ring-blue-500 outline-none"
                    >
                      {ROLES.map(role => <option key={role} value={role}>{role.replace('_', ' ').toUpperCase()}</option>)}
                    </select>
                  </div>
                </div>
                <div className="flex justify-end gap-3 mt-6">
                  <button onClick={() => setShowEditModal(false)} className="px-4 py-2 rounded-lg text-gray-600 hover:bg-gray-100 transition-colors">Hủy</button>
                  <button onClick={handleEditRole} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-medium transition-colors">Cập nhật</button>
                </div>
              </div>
            </div>
          )}

          {/* Reset Password Result Modal */}
          {showResetPasswordModal && (
            <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
              <div className="bg-white p-8 rounded-xl shadow-2xl border border-gray-200 w-full max-w-md text-center">
                <CheckCircle2 className="w-16 h-16 text-green-500 mx-auto mb-4" />
                <h2 className="text-xl font-bold text-gray-800 mb-3">Mật khẩu đã được đặt lại!</h2>
                <p className="text-gray-600 mb-4">
                  Mật khẩu mới cho người dùng <span className="font-semibold text-blue-600">{resetPasswordResult.username}</span> là:
                </p>
                <div className="bg-gray-100 border border-gray-300 rounded-lg px-4 py-3 mb-6">
                  <p className="font-mono text-lg text-green-700 break-all">{resetPasswordResult.newPassword}</p>
                </div>
                <p className="text-sm text-red-600 mb-6">
                  Vui lòng sao chép mật khẩu này ngay lập tức. Nó sẽ không được hiển thị lại.
                </p>
                <button onClick={() => setShowResetPasswordModal(false)} className="px-6 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-medium transition-colors">Đóng</button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Audit Log Tab */}
      {activeTab === 'audit' && (
        <>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <History className="w-8 h-8 text-amber-500" />
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Audit Log</h1>
                <p className="text-sm text-gray-500">Lịch sử thao tác người dùng</p>
              </div>
            </div>
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700"
            >
              <option value="">Tất cả hành động</option>
              {Object.entries(ACTION_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>

          <div className="bg-white border border-gray-100 rounded-xl overflow-hidden flex-1 flex flex-col" style={{ maxHeight: 'calc(100vh - 300px)' }}>
            {logsLoading ? (
              <p className="p-6 text-gray-400">Đang tải...</p>
            ) : (
              <>
                <div className="overflow-auto flex-1">
                  <table className="w-full text-left text-sm text-gray-700">
                    <thead className="bg-gray-50 text-xs uppercase text-gray-600 sticky top-0">
                      <tr>
                        <th className="px-4 py-3">Thời gian</th>
                        <th className="px-4 py-3">User</th>
                        <th className="px-4 py-3">Hành động</th>
                        <th className="px-4 py-3">Resource</th>
                        <th className="px-4 py-3">Chi tiết</th>
                        <th className="px-4 py-3">IP</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                    {logs.length === 0 ? (
                      <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-500">Chưa có audit log</td></tr>
                    ) : logs.map((log) => (
                      <tr key={log.id} className="hover:bg-gray-50">
                        <td className="px-4 py-2 text-xs text-gray-600">{formatDatetime(log.created_at)}</td>
                        <td className="px-4 py-2 font-medium text-gray-800">{log.username}</td>
                        <td className="px-4 py-2">
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-amber-100 text-amber-700 text-xs">
                            <Shield className="w-3 h-3" />
                            {ACTION_LABELS[log.action] || log.action}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-xs text-gray-500">
                          {log.resource_type ? `${log.resource_type}${log.resource_id ? ` #${log.resource_id}` : ''}` : '—'}
                        </td>
                        <td className="px-4 py-2 text-[10px] font-mono text-gray-500 max-w-[200px] truncate">
                          {log.details ? JSON.stringify(log.details) : '—'}
                        </td>
                        <td className="px-4 py-2 font-mono text-xs text-gray-600">{log.client_ip || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                </div>
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
        </>
      )}
    </div>
  );
}
