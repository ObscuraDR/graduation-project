import React, { useState } from 'react';
import { User, Lock, Save, ShieldCheck, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import api from '../lib/api';
import { getUser } from '../lib/auth';

export default function ProfileSettings() {
  const user = getUser();
  const [formData, setFormData] = useState({
    old_password: '',
    new_password: '',
    confirm_password: ''
  });
  
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage({ type: '', text: '' });

    if (formData.new_password !== formData.confirm_password) {
      setMessage({ type: 'error', text: 'Mật khẩu mới không khớp nhau' });
      return;
    }

    // Cập nhật kiểm tra độ mạnh mật khẩu khớp với Backend
    const passwordRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$/;
    if (formData.new_password.length < 8 || !passwordRegex.test(formData.new_password)) {
      setMessage({ 
        type: 'error', 
        text: 'Mật khẩu mới phải có ít nhất 8 ký tự, bao gồm chữ hoa, chữ thường và số.' 
      });
      return;
    }

    setLoading(true);
    try {
      await api.post('/auth/change-password', {
        old_password: formData.old_password,
        new_password: formData.new_password,
      });

      setMessage({ type: 'success', text: 'Đổi mật khẩu thành công!' });
      setFormData({ old_password: '', new_password: '', confirm_password: '' });
    } catch (err) {
      const errorMsg = err.response?.data?.detail || 'Có lỗi xảy ra, vui lòng thử lại';
      setMessage({ type: 'error', text: errorMsg });
    } finally {
      setLoading(false);
    }
  };

  const inputClass = "w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-slate-200 placeholder-slate-600 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2.5 rounded-xl bg-blue-500/10 border border-blue-500/20">
          <User className="w-6 h-6 text-blue-400" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Cài đặt tài khoản</h1>
          <p className="text-sm text-slate-500 mt-0.5">Quản lý thông tin cá nhân và bảo mật</p>
        </div>
      </div>

      {/* Thông tin cá nhân (Read-only) */}
      <div className="bg-slate-900/60 backdrop-blur-sm rounded-2xl p-6 border border-slate-800/60 space-y-4">
        <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-emerald-400" /> Thông tin cá nhân
        </h2>
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-slate-800/40 border border-slate-700/40 rounded-xl p-4">
            <label className="block text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Tên đăng nhập</label>
            <p className="text-slate-200 font-medium">{user?.username}</p>
          </div>
          <div className="bg-slate-800/40 border border-slate-700/40 rounded-xl p-4">
            <label className="block text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Vai trò</label>
            <span className="inline-block mt-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 capitalize">
              {user?.role}
            </span>
          </div>
        </div>
      </div>

      {/* Form đổi mật khẩu */}
      <form onSubmit={handleSubmit} className="bg-slate-900/60 backdrop-blur-sm rounded-2xl p-6 border border-slate-800/60 space-y-5">
        <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
          <Lock className="w-5 h-5 text-blue-400" /> Đổi mật khẩu
        </h2>

        {message.text && (
          <div className={`p-4 rounded-xl flex items-center gap-3 border ${
            message.type === 'success' 
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' 
              : 'bg-red-500/10 border-red-500/30 text-red-400'
          }`}>
            {message.type === 'success' ? <CheckCircle2 className="w-5 h-5 flex-shrink-0" /> : <AlertCircle className="w-5 h-5 flex-shrink-0" />}
            <span className="text-sm font-medium">{message.text}</span>
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-1.5">Mật khẩu hiện tại</label>
            <input type="password" name="old_password" value={formData.old_password} onChange={handleChange}
              required className={inputClass} placeholder="••••••••" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-1.5">Mật khẩu mới</label>
            <input type="password" name="new_password" value={formData.new_password} onChange={handleChange}
              required className={inputClass} placeholder="••••••••" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-1.5">Xác nhận mật khẩu mới</label>
            <input type="password" name="confirm_password" value={formData.confirm_password} onChange={handleChange}
              required className={inputClass} placeholder="••••••••" />
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-600/50 text-white font-bold py-3 rounded-xl transition-all shadow-lg shadow-blue-500/20"
        >
          {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Save className="w-5 h-5" />}
          {loading ? 'Đang xử lý...' : 'Cập nhật mật khẩu'}
        </button>
      </form>
    </div>
  );
}