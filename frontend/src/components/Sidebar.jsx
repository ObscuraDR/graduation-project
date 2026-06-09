import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  Shield, LayoutDashboard, AlertTriangle, Server, Settings,
  LogOut, User, Globe, Bell, Brain, Network, FileText,
  Users, // Add Users icon
} from 'lucide-react';
import { getUser, logout, hasRole } from '../lib/auth';

export default function Sidebar() {
  const user = getUser();

  const navItems = [
    { to: '/', icon: LayoutDashboard, label: 'Tổng quan' },
    { to: '/alerts', icon: AlertTriangle, label: 'Cảnh báo' },
    { to: '/firewall', icon: Shield, label: 'Firewall' },
    { to: '/servers', icon: Server, label: 'Máy chủ' },
    { to: '/network', icon: Network, label: 'Lưu lượng' },
    { to: '/ai-insights', icon: Brain, label: 'AI Insights' },
    { to: '/reports', icon: FileText, label: 'Báo cáo' },
  ];

  const settingsItems = [
    { to: '/settings/profile', icon: User, label: 'Tài khoản' },
    { to: '/settings/notifications', icon: Bell, label: 'Thông báo' }, // FR09
    { to: '/geo-blocking', icon: Globe, label: 'Geo Blocking', roles: ['admin'] }, // FR04 - Dedicated page
    { to: '/settings/users', icon: Users, label: 'Quản lý User', roles: ['admin'] }, // FR01
  ];

  return (
    <div className="w-64 bg-gray-800 text-gray-200 flex flex-col p-4 shadow-lg">
      {/* Logo */}
      <div className="flex items-center gap-3 mb-8 px-2">
        <div className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-blue-600/20">
          <Shield className="w-6 h-6 text-blue-400" />
        </div>
        <span className="text-xl font-bold text-white">Z-Sentinel</span>
      </div>

      {/* Main Navigation */}
      <nav className="flex-1 space-y-2">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex items-center gap-3 p-3 rounded-lg transition-colors ${
                isActive ? 'bg-blue-700 text-white shadow-md' : 'hover:bg-gray-700'
              }`
            }
          >
            <item.icon className="w-5 h-5" />
            <span className="text-sm font-medium">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Settings Section */}
      <div className="mt-8 pt-4 border-t border-gray-700 space-y-2">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider px-3 mb-2">Cài đặt</h3>
        {settingsItems.map((item) => (
          // Chỉ hiển thị nếu người dùng có quyền hoặc không yêu cầu quyền cụ thể
          (!item.roles || hasRole(item.roles)) && (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 p-3 rounded-lg transition-colors ${
                  isActive ? 'bg-blue-700 text-white shadow-md' : 'hover:bg-gray-700'
                }`
              }
            >
              <item.icon className="w-5 h-5" />
              <span className="text-sm font-medium">{item.label}</span>
            </NavLink>
          )
        ))}
      </div>

      {/* User Info and Logout */}
      <div className="mt-auto pt-4 border-t border-gray-700">
        {user && (
          <div className="flex items-center gap-3 p-3 rounded-lg bg-gray-700 mb-2">
            <User className="w-5 h-5 text-gray-400" />
            <div>
              <p className="text-sm font-medium text-white">{user.username}</p>
              <p className="text-xs text-gray-400 capitalize">{user.role}</p>
            </div>
          </div>
        )}
        <button
          onClick={logout}
          className="flex items-center gap-3 p-3 rounded-lg w-full text-left hover:bg-red-700 transition-colors text-red-300"
        >
          <LogOut className="w-5 h-5" />
          <span className="text-sm font-medium">Đăng xuất</span>
        </button>
      </div>
    </div>
  );
}