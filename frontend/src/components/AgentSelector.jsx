import React, { useEffect, useState } from 'react';
import { Server } from 'lucide-react';
import { fetchAgents } from '../lib/api';

export default function AgentSelector({ value, onChange }) {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const loadAgents = async () => {
      setLoading(true);
      try {
        const data = await fetchAgents();
        setAgents(data);
      } catch (err) {
        console.error('Failed to load agents', err);
      } finally {
        setLoading(false);
      }
    };
    loadAgents();
  }, []);

  return (
    <div className="flex items-center gap-2">
      <Server className="w-4 h-4 text-slate-400" />
      <select
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        disabled={loading}
        className="bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block p-2 transition-colors outline-none"
      >
        <option value="">Tất cả Agents</option>
        {agents.map((agent) => (
          <option key={agent.id} value={agent.id}>
            {agent.name} {agent.ip_address ? `(${agent.ip_address})` : ''} - {agent.status === 'online' ? '🟢' : '🔴'}
          </option>
        ))}
      </select>
    </div>
  );
}
