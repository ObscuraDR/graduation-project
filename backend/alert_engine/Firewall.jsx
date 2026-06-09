import React, { useEffect, useState } from 'react';
import { ShieldAlert, Trash2, Clock } from 'lucide-react';
import { getBlacklist, unblockIP } from '../lib/api';
import { hasRole } from '../lib/auth';

export default function Firewall() {
  const [blacklist, setBlacklist] = useState([]);

  useEffect(() => {
    fetchBlacklist();
  }, []);

  const fetchBlacklist = async () => {
    const data = await getBlacklist();
    setBlacklist(data);
  };

  const handleUnblock = async (ip) => {
    if (window.confirm(`Bạn có chắc muốn gỡ chặn IP ${ip}?`)) {
      await unblockIP(ip);
      fetchBlacklist();
    }
  };

  return (
    <div className="p-6">
      <div className="flex items-center gap-3 mb-6">
        <ShieldAlert className="w-8 h-8 text-red-500" />
        <h1 className="text-2xl font-bold text-white">Quản lý Firewall</h1>
      </div>

      <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <table className="w-full text-left text-gray-300">
          <thead className="bg-gray-900/50 text-gray-400 text-xs uppercase">
            <tr>
              <th className="px-6 py-4">Địa chỉ IP</th>
              <th className="px-6 py-4">Lý do</th>
              <th className="px-6 py-4">Thời gian chặn</th>
              <th className="px-6 py-4">Hết hạn (Dự kiến)</th>
              <th className="px-6 py-4 text-right">Thao tác</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {blacklist.map((item) => (
              <tr key={item.ip_address} className="hover:bg-gray-750">
                <td className="px-6 py-4 font-mono text-blue-400">{item.ip_address}</td>
                <td className="px-6 py-4 text-sm">{item.reason}</td>
                <td className="px-6 py-4 text-xs">{new Date(item.blocked_at).toLocaleString()}</td>
                <td className="px-6 py-4 text-xs text-orange-400">
                  <Clock className="w-3 h-3 inline mr-1" />
                  {item.expires_at ? new Date(item.expires_at).toLocaleString() : 'Vĩnh viễn'}
                </td>
                <td className="px-6 py-4 text-right">
                  {hasRole(['admin', 'security_analyst']) && (
                    <button onClick={() => handleUnblock(item.ip_address)} className="text-red-400 hover:text-red-300">
                      <Trash2 className="w-5 h-5" />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}