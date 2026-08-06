import React, { useState, useEffect } from 'react';
import { Send, Bell, Save, CheckCircle, Mail } from 'lucide-react';
import api from '../lib/api';

export default function NotificationSettings() {
  const [settings, setSettings] = useState({
    email_enabled: false,
    smtp_to: '',
    telegram_enabled: false,
    telegram_bot_token: '',
    telegram_chat_id: '',
    discord_enabled: false,
    discord_webhook_url: '',
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    api.get('/settings/notifications')
      .then((res) => setSettings((prev) => ({ ...prev, ...res.data })))
      .catch(console.error);
  }, []);

  const handleSave = async () => {
    setLoading(true);
    try {
      await api.post('/settings/notifications', settings);
      setMessage('Đã lưu cấu hình thành công!');
      setTimeout(() => setMessage(''), 3000);
    } catch (err) {
      setMessage('Lỗi khi lưu cấu hình');
      setTimeout(() => setMessage(''), 3000);
    } finally {
      setLoading(false);
    }
  };

  const inputClass = "w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-slate-200 placeholder-slate-600 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
  const labelClass = "block text-sm font-medium text-slate-400 mb-2"

  const Toggle = ({ checked, onChange, color = 'blue' }) => (
    <label className="relative inline-flex items-center cursor-pointer">
      <input type="checkbox" checked={checked} onChange={onChange} className="sr-only peer" />
      <div className={`w-11 h-6 bg-slate-700 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-${color}-600`} />
    </label>
  )

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2.5 rounded-xl bg-blue-500/10 border border-blue-500/20">
          <Bell className="w-6 h-6 text-blue-400" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Cấu hình Thông báo</h1>
          <p className="text-sm text-slate-500 mt-0.5">Email · Telegram Bot · Discord Webhook</p>
        </div>
      </div>

      {message && (
        <div className={`p-4 rounded-xl flex items-center gap-2 ${
          message.includes('Lỗi')
            ? 'bg-red-500/10 border border-red-500/30 text-red-400'
            : 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400'
        }`}>
          <CheckCircle className="w-5 h-5 flex-shrink-0" /> {message}
        </div>
      )}

      <div className="space-y-4">

        {/* ── Email ── */}
        <div className="bg-slate-900/60 backdrop-blur-sm p-6 rounded-xl border border-slate-800/60">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
              <Mail className="w-5 h-5 text-red-400" /> Email Alert
            </h2>
            <Toggle
              checked={settings.email_enabled}
              onChange={(e) => setSettings({ ...settings, email_enabled: e.target.checked })}
              color="red"
            />
          </div>
          <div className="space-y-4">
            <div>
              <label className={labelClass}>Địa chỉ nhận email (có thể nhiều, cách nhau bằng dấu phẩy)</label>
              <input
                type="email"
                value={settings.smtp_to}
                onChange={(e) => setSettings({ ...settings, smtp_to: e.target.value })}
                className={inputClass}
                placeholder="nhungthihongnguyen06@gmail.com, soc@example.com"
                disabled={!settings.email_enabled}
              />
            </div>
            <p className="text-xs text-slate-500">
              Email chỉ gửi khi mức độ <span className="text-orange-400 font-medium">high</span> hoặc <span className="text-red-400 font-medium">critical</span> và độ tin cậy ≥ 85%.
              Cấu hình SMTP (host, user, password) chỉnh trong file <code className="text-slate-300">.env</code>.
            </p>
          </div>
        </div>

        {/* ── Telegram ── */}
        <div className="bg-slate-900/60 backdrop-blur-sm p-6 rounded-xl border border-slate-800/60">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
              <Send className="w-5 h-5 text-sky-400" /> Telegram Bot
            </h2>
            <Toggle
              checked={settings.telegram_enabled}
              onChange={(e) => setSettings({ ...settings, telegram_enabled: e.target.checked })}
              color="blue"
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Bot Token</label>
              <input
                type="password"
                value={settings.telegram_bot_token}
                onChange={(e) => setSettings({ ...settings, telegram_bot_token: e.target.value })}
                className={inputClass}
                placeholder="123456789:ABCDEF..."
                disabled={!settings.telegram_enabled}
              />
            </div>
            <div>
              <label className={labelClass}>Chat ID</label>
              <input
                type="text"
                value={settings.telegram_chat_id}
                onChange={(e) => setSettings({ ...settings, telegram_chat_id: e.target.value })}
                className={inputClass}
                placeholder="-100123456789"
                disabled={!settings.telegram_enabled}
              />
            </div>
          </div>
        </div>

        {/* ── Discord ── */}
        <div className="bg-slate-900/60 backdrop-blur-sm p-6 rounded-xl border border-slate-800/60">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
              <div className="w-5 h-5 bg-indigo-500 rounded-sm flex-shrink-0" /> Discord Webhook
            </h2>
            <Toggle
              checked={settings.discord_enabled}
              onChange={(e) => setSettings({ ...settings, discord_enabled: e.target.checked })}
              color="indigo"
            />
          </div>
          <div>
            <label className={labelClass}>Webhook URL</label>
            <input
              type="password"
              value={settings.discord_webhook_url}
              onChange={(e) => setSettings({ ...settings, discord_webhook_url: e.target.value })}
              className={inputClass}
              placeholder="https://discord.com/api/webhooks/..."
              disabled={!settings.discord_enabled}
            />
          </div>
        </div>

        <button
          onClick={handleSave}
          disabled={loading}
          type="button"
          className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 px-6 rounded-xl flex items-center justify-center gap-2 transition-all disabled:opacity-60 shadow-lg shadow-blue-500/20"
        >
          <Save className="w-5 h-5" />
          {loading ? 'Đang lưu...' : 'Lưu Cấu Hình'}
        </button>
      </div>
    </div>
  );
}
