import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  Shield, LayoutDashboard, AlertTriangle, Server, Settings,
  LogOut, User, Globe, Bell, Brain, Network, FileText, ScrollText,
  Users, History,
} from 'lucide-react';
import { getUser, logout, hasRole } from '../lib/auth';

export default function Sidebar() {
  const user = getUser();

  const navItems = [
    { to: '/', icon: LayoutDashboard, label: 'Tổng quan', end: true },
    { to: '/alerts', icon: AlertTriangle, label: 'Cảnh báo' },
    { to: '/firewall', icon: Shield, label: 'Firewall' },
    { to: '/servers', icon: Server, label: 'Máy chủ' },
    { to: '/traffic', icon: Network, label: 'Lưu lượng' },
    { to: '/logs', icon: ScrollText, label: 'Log Viewer' },
    { to: '/ai-insights', icon: Brain, label: 'AI Insights' },
    { to: '/reports', icon: FileText, label: 'Báo cáo' },
  ];

  const settingsItems = [
    { to: '/settings/profile',       icon: User,   label: 'Tài khoản',         end: true },
    { to: '/audit',                  icon: History, label: 'Audit Log',         end: true, roles: ['admin'] },
    { to: '/settings/notifications', icon: Bell,   label: 'Thông báo',         end: true },
    { to: '/geo-blocking',           icon: Globe,  label: 'Geo Blocking',      end: true, roles: ['admin'] },
    { to: '/settings/users',         icon: Users,  label: 'Quản lý User',      end: true, roles: ['admin'] },
  ];

  return (
    <div className="w-64 bg-slate-900/80 backdrop-blur-xl text-slate-300 flex flex-col p-4 shadow-2xl shadow-black/20 h-screen sticky top-0 overflow-y-auto border-r border-slate-800/50">
      {/* Logo */}
      <div className="flex items-center gap-3 mb-8 px-2">
        <div className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-blue-400 shadow-lg shadow-blue-500/20">
          <Shield className="w-6 h-6 text-white" />
        </div>
        <span className="text-xl font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">Z-Sentinel</span>
      </div>

      {/* Main Navigation */}
      <nav className="flex-1 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 ${
                isActive
                  ? 'bg-blue-600/20 text-blue-400 shadow-sm shadow-blue-500/10 border border-blue-500/20'
                  : 'hover:bg-slate-800/60 hover:text-slate-100 border border-transparent'
              }`
            }
          >
            <item.icon className="w-5 h-5" />
            <span className="text-sm font-medium">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Settings Section */}
      <div className="mt-6 pt-4 border-t border-slate-800/60 space-y-1">
        <h3 className="text-xs font-semibold text-slate-600 uppercase tracking-wider px-3 mb-2">Cài đặt</h3>
        {settingsItems.map((item) => (
          (!item.roles || hasRole(item.roles)) && (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 ${
                  isActive
                    ? 'bg-blue-600/20 text-blue-400 shadow-sm shadow-blue-500/10 border border-blue-500/20'
                    : 'hover:bg-slate-800/60 hover:text-slate-100 border border-transparent'
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
      <div className="mt-auto pt-4 border-t border-slate-800/60">
        {user && (
          <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-slate-800/40 mb-2">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center text-white text-sm font-bold">
              {user.username?.charAt(0)?.toUpperCase() || 'U'}
            </div>
            <div>
              <p className="text-sm font-medium text-slate-200">{user.username}</p>
              <p className="text-xs text-slate-500 capitalize">{user.role}</p>
            </div>
          </div>
        )}
        <button
          onClick={logout}
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg w-full text-left hover:bg-red-500/10 transition-all duration-200 text-red-400 border border-transparent hover:border-red-500/20"
        >
          <LogOut className="w-5 h-5" />
          <span className="text-sm font-medium">Đăng xuất</span>
        </button>
      </div>
    </div>
  );
}