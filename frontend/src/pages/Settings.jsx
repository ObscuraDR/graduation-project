import { useEffect, useState } from 'react'
import { Play, Square, Key, Wifi } from 'lucide-react'
import { fetchSnifferStatus, startSniffer, stopSniffer, fetchHealthDetailed, fetchWhitelist, addWhitelist, removeWhitelist } from '../lib/api'

export default function Settings() {
  const [status, setStatus] = useState(null)
  const [health, setHealth] = useState(null)
  const [apiKey, setApiKey] = useState(localStorage.getItem('ids_api_key') || '')
  const [snifferConfig, setSnifferConfig] = useState({
    interface: 'eth0',
    model_name: 'ensemble',
    min_packets: 10,
    prediction_mode: 'once',
    dry_run: false,
  })
  const [whitelist, setWhitelist] = useState([])
  const [newIp, setNewIp] = useState('')
  const [message, setMessage] = useState(null)

  useEffect(() => {
    loadStatus()
    fetchHealthDetailed().then(setHealth).catch(() => {})
    fetchWhitelist().then((res) => setWhitelist(res.data?.items || [])).catch(() => {})
  }, [])

  const loadStatus = () => {
    fetchSnifferStatus().then(setStatus).catch(() => setStatus(null))
  }

  const handleSaveApiKey = () => {
    localStorage.setItem('ids_api_key', apiKey)
    setMessage({ type: 'success', text: 'API Key saved to browser' })
    setTimeout(() => setMessage(null), 3000)
  }

  const handleStart = async () => {
    try {
      await startSniffer(snifferConfig)
      setMessage({ type: 'success', text: 'Pipeline started successfully' })
      loadStatus()
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || err.message })
    }
  }

  const handleStop = async () => {
    try {
      await stopSniffer()
      setMessage({ type: 'success', text: 'Pipeline stopped' })
      loadStatus()
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || err.message })
    }
  }

  const handleAddWhitelist = async () => {
    if (!newIp) return
    try {
      await addWhitelist({ ip_address: newIp, reason: 'Added from dashboard' })
      setNewIp('')
      fetchWhitelist().then((res) => setWhitelist(res.data?.items || []))
      setMessage({ type: 'success', text: `${newIp} added to whitelist` })
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.message || err.message })
    }
  }

  const handleRemoveWhitelist = async (id) => {
    try {
      await removeWhitelist({ whitelist_id: id })
      fetchWhitelist().then((res) => setWhitelist(res.data?.items || []))
    } catch (err) {
      console.error(err)
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <h1 className="text-2xl font-bold text-gray-900">Settings</h1>

      {message && (
        <div className={`p-3 rounded-lg text-sm ${message.type === 'success' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'}`}>
          {message.text}
        </div>
      )}

      {/* API Key */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
          <Key className="w-4 h-4" /> API Key Configuration
        </h3>
        <div className="flex gap-3">
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="Enter your X-API-Key"
            className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm"
          />
          <button onClick={handleSaveApiKey} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
            Save
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-2">Stored in browser localStorage. Required for sniffer control. Default: <code className="bg-gray-100 px-1 rounded">supersecretkey</code></p>
      </div>

      {/* Service Health */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
          <Wifi className="w-4 h-4" /> Service Health
        </h3>
        {health ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { name: 'PostgreSQL', ok: health.postgres?.connected },
              { name: 'Redis', ok: health.redis?.connected },
              { name: 'MongoDB', ok: health.mongo?.connected },
              { name: 'ML Model', ok: health.model_loaded },
            ].map(({ name, ok }) => (
              <div key={name} className="flex items-center gap-2 p-2 rounded-lg bg-gray-50">
                <span className={`w-2.5 h-2.5 rounded-full ${ok ? 'bg-green-500' : 'bg-red-500'}`} />
                <span className="text-sm text-gray-700">{name}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-400">Unable to fetch health status</p>
        )}
      </div>

      {/* Pipeline Control */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Pipeline Control</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
          <div>
            <label className="text-xs text-gray-500">Interface</label>
            <input
              value={snifferConfig.interface}
              onChange={(e) => setSnifferConfig((c) => ({ ...c, interface: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm mt-1"
            />
          </div>
          <div>
            <label className="text-xs text-gray-500">Model</label>
            <input
              value={snifferConfig.model_name}
              onChange={(e) => setSnifferConfig((c) => ({ ...c, model_name: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm mt-1"
            />
          </div>
          <div>
            <label className="text-xs text-gray-500">Min Packets</label>
            <input
              type="number"
              value={snifferConfig.min_packets}
              onChange={(e) => setSnifferConfig((c) => ({ ...c, min_packets: parseInt(e.target.value) || 10 }))}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm mt-1"
            />
          </div>
        </div>
        <div className="flex gap-3">
          <button
            onClick={handleStart}
            disabled={status?.is_running}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 disabled:opacity-50"
          >
            <Play className="w-4 h-4" /> Start Pipeline
          </button>
          <button
            onClick={handleStop}
            disabled={!status?.is_running}
            className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700 disabled:opacity-50"
          >
            <Square className="w-4 h-4" /> Stop Pipeline
          </button>
        </div>
        {status && (
          <p className="text-xs text-gray-500 mt-3">
            Status: {status.is_running ? '🟢 Running' : '⚪ Stopped'} | Packets: {status.processed_packets || 0} | Inferences: {status.inference_runs || 0}
          </p>
        )}
      </div>

      {/* Whitelist */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">IP Whitelist</h3>
        <div className="flex gap-3 mb-4">
          <input
            value={newIp}
            onChange={(e) => setNewIp(e.target.value)}
            placeholder="192.168.1.100"
            className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm"
          />
          <button onClick={handleAddWhitelist} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
            Add
          </button>
        </div>
        {whitelist.length > 0 ? (
          <div className="space-y-2">
            {whitelist.map((item) => (
              <div key={item.id} className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg">
                <div>
                  <span className="text-sm font-mono">{item.ip_address}</span>
                  {item.reason && <span className="text-xs text-gray-400 ml-2">— {item.reason}</span>}
                </div>
                <button onClick={() => handleRemoveWhitelist(item.id)} className="text-xs text-red-500 hover:text-red-700">
                  Remove
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-400">No whitelisted IPs</p>
        )}
      </div>
    </div>
  )
}
