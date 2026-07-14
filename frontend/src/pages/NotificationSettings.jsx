import React, { useState, useEffect } from 'react';
import { Send, Bell, Save, CheckCircle, Mail, AlertCircle, Loader2, TestTube } from 'lucide-react';
import api from '../lib/api';

const inputClass = "w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-slate-200 placeholder-slate-600 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all";
const labelClass = "block text-sm font-medium text-slate-400 mb-2";

function Toggle({ checked, onChange, color = 'blue' }) {
  return (
    <label className="relative inline-flex items-center cursor-pointer">
      <input type="checkbox" checked={checked} onChange={onChange} className="sr-only peer" />
      <div className={`w-11 h-6 bg-slate-700 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-${color}-600`} />
    </label>
  );
}

export default function NotificationSettings() {
  const [settings, setSettings] = useState({
    // Email
    email_enabled: false,
    smtp_host: 'smtp.gmail.com',
    smtp_port: 587,
    smtp_user: '',
    smtp_password: '',
    smtp_from: '',
    smtp_to: '',
    email_cooldown_seconds: 60,
    // Telegram
    telegram_enabled: false,
    telegram_bot_token: '',
    telegram_chat_id: '',
    // Discord
    discord_enabled: false,
    discord_webhook_url: '',
  });
  const [loading, setLoading] = useState(false);
  const [testLoading, setTestLoading] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  useEffect(() => {
    api.get('/settings/notifications')
      .then((res) => setSettings(prev => ({ ...prev, ...res.data })))
      .catch(console.error);
  }, []);

  const set = (key, val) => setSettings(prev => ({ ...prev, [key]: val }));

  const showMsg = (type, text) => {
    setMessage({ type, text });
    setTimeout(() => setMessage({ type: '', text: '' }), 4000);
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      await api.post('/settings/notifications', settings);
      showMsg('success', 'Cấu hình thông báo đã được lưu thành công!');
    } catch (err) {
      showMsg('error', err.response?.data?.detail || 'Lỗi khi lưu cấu hình');
    } finally {
      setLoading(false);
    }
  };

  const handleTestEmail = async () => {
    setTestLoading(true);
    try {
      // Lưu trước khi test
      await api.post('/settings/notifications', settings);
      const res = await api.post('/settings/notifications/test-email');
      showMsg('success', res.data.message);
    } catch (err) {
      showMsg('error', err.response?.data?.detail || 'Gửi email test thất bại');
    } finally {
      setTestLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2.5 rounded-xl bg-blue-500/10 border border-blue-500/20">
          <Bell className="w-6 h-6 text-blue-400" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Cấu hình Thông báo</h1>
          <p className="text-sm text-slate-500 mt-0.5">Email, Telegram Bot & Discord Webhook</p>
        </div>
      </div>

      {/* Message */}
      {message.text && (
        <div className={`p-4 rounded-xl flex items-center gap-2 ${
          message.type === 'success'
            ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400'
            : 'bg-red-500/10 border border-red-500/30 text-red-400'
        }`}>
          {message.type === 'success'
            ? <CheckCircle className="w-5 h-5 flex-shrink-0" />
            : <AlertCircle className="w-5 h-5 flex-shrink-0" />}
          {message.text}
        </div>
      )}

      {/* ── EMAIL ─────────────────────────────────────────────────────── */}
      <div className="bg-slate-900/60 backdrop-blur-sm p-6 rounded-xl border border-slate-800/60">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
            <Mail className="w-5 h-5 text-emerald-400" /> Email (SMTP)
          </h2>
          <Toggle
            checked={settings.email_enabled}
            onChange={(e) => set('email_enabled', e.target.checked)}
            color="emerald"
          />
        </div>

        <div className={`space-y-4 ${!settings.email_enabled ? 'opacity-40 pointer-events-none' : ''}`}>
          {/* SMTP Host + Port */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="md:col-span-2">
              <label className={labelClass}>SMTP Host</label>
              <input
                type="text"
                value={settings.smtp_host}
                onChange={(e) => set('smtp_host', e.target.value)}
                className={inputClass}
                placeholder="smtp.gmail.com"
              />
            </div>
            <div>
              <label className={labelClass}>Port</label>
              <input
                type="number"
                value={settings.smtp_port}
                onChange={(e) => set('smtp_port', parseInt(e.target.value))}
                className={inputClass}
                placeholder="587"
              />
            </div>
          </div>

          {/* Email + Password */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Email (tài khoản gửi)</label>
              <input
                type="email"
                value={settings.smtp_user}
                onChange={(e) => set('smtp_user', e.target.value)}
                className={inputClass}
                placeholder="your-email@gmail.com"
              />
            </div>
            <div>
              <label className={labelClass}>App Password</label>
              <input
                type="password"
                value={settings.smtp_password}
                onChange={(e) => set('smtp_password', e.target.value)}
                className={inputClass}
                placeholder="Gmail App Password (16 ký tự)"
              />
            </div>
          </div>

          {/* From + To */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Tên hiển thị (From)</label>
              <input
                type="text"
                value={settings.smtp_from}
                onChange={(e) => set('smtp_from', e.target.value)}
                className={inputClass}
                placeholder="Z-Sentinel IDS <noreply@...>"
              />
            </div>
            <div>
              <label className={labelClass}>Gửi đến (To) — cách nhau bằng dấu phẩy</label>
              <input
                type="text"
                value={settings.smtp_to}
                onChange={(e) => set('smtp_to', e.target.value)}
                className={inputClass}
                placeholder="admin@example.com, soc@example.com"
              />
            </div>
          </div>

          {/* Cooldown */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Cooldown giữa các email (giây)</label>
              <input
                type="number"
                value={settings.email_cooldown_seconds}
                onChange={(e) => set('email_cooldown_seconds', parseInt(e.target.value))}
                className={inputClass}
                min={10}
                placeholder="60"
              />
              <p className="text-xs text-slate-600 mt-1">
                Thời gian tối thiểu giữa 2 email cùng IP tấn công (anti-spam)
              </p>
            </div>
          </div>

          {/* Hướng dẫn Gmail */}
          <div className="bg-slate-800/40 rounded-lg p-4 text-sm text-slate-400">
            <p className="font-medium text-slate-300 mb-2">📋 Hướng dẫn Gmail App Password:</p>
            <ol className="list-decimal list-inside space-y-1">
              <li>Vào <strong className="text-slate-300">Google Account</strong> → Security</li>
              <li>Bật <strong className="text-slate-300">2-Step Verification</strong></li>
              <li>Tìm <strong className="text-slate-300">App passwords</strong> → Tạo mới</li>
              <li>Copy 16 ký tự và dán vào ô App Password ở trên</li>
            </ol>
          </div>

          {/* Test button */}
          <button
            onClick={handleTestEmail}
            disabled={testLoading || !settings.smtp_user || !settings.smtp_to}
            type="button"
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 border border-emerald-500/30 transition-all disabled:opacity-50 text-sm font-medium"
          >
            {testLoading
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <TestTube className="w-4 h-4" />}
            {testLoading ? 'Đang gửi...' : 'Gửi Email Test'}
          </button>
        </div>
      </div>

      {/* ── TELEGRAM ──────────────────────────────────────────────────── */}
      <div className="bg-slate-900/60 backdrop-blur-sm p-6 rounded-xl border border-slate-800/60">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
            <Send className="w-5 h-5 text-sky-400" /> Telegram Bot
            <span className="text-xs text-slate-600 font-normal">(sắp ra mắt)</span>
          </h2>
          <Toggle
            checked={settings.telegram_enabled}
            onChange={(e) => set('telegram_enabled', e.target.checked)}
            color="blue"
          />
        </div>
        <div className={`grid grid-cols-1 md:grid-cols-2 gap-4 ${!settings.telegram_enabled ? 'opacity-40 pointer-events-none' : ''}`}>
          <div>
            <label className={labelClass}>Bot Token</label>
            <input
              type="password"
              value={settings.telegram_bot_token}
              onChange={(e) => set('telegram_bot_token', e.target.value)}
              className={inputClass}
              placeholder="123456789:ABCDEF..."
            />
          </div>
          <div>
            <label className={labelClass}>Chat ID</label>
            <input
              type="text"
              value={settings.telegram_chat_id}
              onChange={(e) => set('telegram_chat_id', e.target.value)}
              className={inputClass}
              placeholder="-100123456789"
            />
          </div>
        </div>
      </div>

      {/* ── DISCORD ───────────────────────────────────────────────────── */}
      <div className="bg-slate-900/60 backdrop-blur-sm p-6 rounded-xl border border-slate-800/60">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
            <div className="w-5 h-5 bg-indigo-500 rounded-sm flex-shrink-0" /> Discord Webhook
            <span className="text-xs text-slate-600 font-normal">(sắp ra mắt)</span>
          </h2>
          <Toggle
            checked={settings.discord_enabled}
            onChange={(e) => set('discord_enabled', e.target.checked)}
            color="indigo"
          />
        </div>
        <div className={`${!settings.discord_enabled ? 'opacity-40 pointer-events-none' : ''}`}>
          <label className={labelClass}>Webhook URL</label>
          <input
            type="password"
            value={settings.discord_webhook_url}
            onChange={(e) => set('discord_webhook_url', e.target.value)}
            className={inputClass}
            placeholder="https://discord.com/api/webhooks/..."
          />
        </div>
      </div>

      {/* Save button */}
      <button
        onClick={handleSave}
        disabled={loading}
        type="button"
        className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 px-6 rounded-xl flex items-center justify-center gap-2 transition-all disabled:opacity-60 shadow-lg shadow-blue-500/20"
      >
        {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Save className="w-5 h-5" />}
        {loading ? 'Đang lưu...' : 'Lưu Cấu Hình'}
      </button>
    </div>
  );
}
