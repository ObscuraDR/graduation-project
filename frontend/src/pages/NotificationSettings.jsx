import React, { useState, useEffect } from 'react';
import { Send, Bell, Save, CheckCircle } from 'lucide-react';
import api from '../lib/api';

export default function NotificationSettings() {
  const [settings, setSettings] = useState({
    telegram_enabled: false,
    telegram_bot_token: '',
    telegram_chat_id: '',
    discord_enabled: false,
    discord_webhook_url: '',
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    api.get('/settings/notifications').then((res) => setSettings(res.data)).catch(console.error);
  }, []);

  const handleSave = async () => {
    setLoading(true);
    try {
      await api.post('/settings/notifications', settings);
      setMessage('Đã lưu cấu hình thành công!');
      setTimeout(() => setMessage(''), 3000);
    } catch (err) {
      alert('Lỗi khi lưu cấu hình');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-center gap-3 mb-8">
        <Bell className="w-8 h-8 text-blue-500" />
        <h1 className="text-2xl font-bold text-white">Cấu hình Thông báo</h1>
      </div>

      {message && (
        <div className="mb-6 p-4 bg-green-500/10 border border-green-500/50 rounded-lg text-green-400 flex items-center gap-2">
          <CheckCircle className="w-5 h-5" /> {message}
        </div>
      )}

      <div className="space-y-6">
        <div className="bg-gray-800 p-6 rounded-xl border border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <Send className="w-5 h-5 text-sky-400" /> Telegram Bot
            </h2>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={settings.telegram_enabled}
                onChange={(e) => setSettings({ ...settings, telegram_enabled: e.target.checked })}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-700 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600" />
            </label>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">Bot Token</label>
              <input
                type="password"
                value={settings.telegram_bot_token}
                onChange={(e) => setSettings({ ...settings, telegram_bot_token: e.target.value })}
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-white focus:ring-2 focus:ring-blue-500 outline-none"
                placeholder="123456789:ABCDEF..."
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">Chat ID</label>
              <input
                type="text"
                value={settings.telegram_chat_id}
                onChange={(e) => setSettings({ ...settings, telegram_chat_id: e.target.value })}
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-white focus:ring-2 focus:ring-blue-500 outline-none"
                placeholder="-100123456789"
              />
            </div>
          </div>
        </div>

        <div className="bg-gray-800 p-6 rounded-xl border border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <div className="w-5 h-5 bg-indigo-500 rounded-sm" /> Discord Webhook
            </h2>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={settings.discord_enabled}
                onChange={(e) => setSettings({ ...settings, discord_enabled: e.target.checked })}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-700 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600" />
            </label>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">Webhook URL</label>
            <input
              type="password"
              value={settings.discord_webhook_url}
              onChange={(e) => setSettings({ ...settings, discord_webhook_url: e.target.value })}
              className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-white focus:ring-2 focus:ring-indigo-500 outline-none"
              placeholder="https://discord.com/api/webhooks/..."
            />
          </div>
        </div>

        <button
          onClick={handleSave}
          disabled={loading}
          type="button"
          className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 px-6 rounded-xl flex items-center justify-center gap-2 transition-all disabled:opacity-60"
        >
          <Save className="w-5 h-5" />
          {loading ? 'Đang lưu...' : 'Lưu Cấu Hình'}
        </button>
      </div>
    </div>
  );
}
