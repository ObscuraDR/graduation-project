﻿import { useEffect, useState } from 'react'
import { Play, Square, Key, Wifi, RefreshCw, Shield, Globe, Ban, Terminal } from 'lucide-react'
import {
  fetchSnifferStatus, startSniffer, stopSniffer, fetchHealthDetailed,
  fetchWhitelist, addWhitelist, removeWhitelist, fetchInterfaces,
  fetchBlacklist, addBlacklist, removeBlacklist,
  fetchGeoBlocks, addGeoBlock, removeGeoBlock,
} from '../lib/api'
import { formatDatetime } from '../lib/datetime'

const TABS = ['Pipeline', 'Whitelist', 'Blacklist', 'Geo Block']

// Common country codes for quick-add
const COMMON_COUNTRIES = [
  { code: 'CN', name: 'China' }, { code: 'RU', name: 'Russia' },
  { code: 'KP', name: 'North Korea' }, { code: 'IR', name: 'Iran' },
  { code: 'VN', name: 'Vietnam' }, { code: 'US', name: 'United States' },
]

export default function Settings() {
  const [tab, setTab] = useState('Pipeline')
  const [status, setStatus] = useState(null)
  const [health, setHealth] = useState(null)
  const [healthCheckedAt, setHealthCheckedAt] = useState(null)
  const [healthLoading, setHealthLoading] = useState(false)
  const [interfaces, setInterfaces] = useState([])
  const [apiKey, setApiKey] = useState(localStorage.getItem('ids_api_key') || '')
  const [snifferConfig, setSnifferConfig] = useState({
    interface: 'Wi-Fi 2', model_name: 'ensemble',
    min_packets: 10, prediction_mode: 'once', dry_run: false,
  })
  const [message, setMessage] = useState(null)
  const [demoEnabled, setDemoEnabled] = useState(false)

  // Whitelist
  const [whitelist, setWhitelist] = useState([])
  const [newWlIp, setNewWlIp] = useState('')

  // Blacklist
  const [blacklist, setBlacklist] = useState([])
  const [newBlIp, setNewBlIp] = useState('')
  const [newBlReason, setNewBlReason] = useState('')
  const [newBlHours, setNewBlHours] = useState('')

  // Geo-block
  const [geoRules, setGeoRules] = useState([])
  const [newCountryCode, setNewCountryCode] = useState('')
  const [newCountryName, setNewCountryName] = useState('')

  const flash = (type, text) => {
    setMessage({ type, text })
    setTimeout(() => setMessage(null), 3500)
  }

  const loadAll = () => {
    fetchSnifferStatus().then(setStatus).catch(() => setStatus(null))
    fetchWhitelist().then((r) => setWhitelist(r.data?.items || [])).catch(() => {})
    fetchBlacklist().then(setBlacklist).catch(() => {})
    fetchGeoBlocks().then(setGeoRules).catch(() => {})
    fetchInterfaces().then((r) => setInterfaces(r.interfaces || [])).catch(() => {})
    // /api/demo/status trả về { running, enable_demo_replay, ... } qua GET
    fetch('/api/demo/status').then(r => r.json()).then(data => {
      // is_running hoặc running — kiểm tra cả hai field
      setDemoEnabled(data.running === true)
    }).catch(() => {})
  }

  const loadHealth = async () => {
    setHealthLoading(true)
    try { const d = await fetchHealthDetailed(); setHealth(d); setHealthCheckedAt(new Date().toLocaleTimeString()) }
    catch {}
    setHealthLoading(false)
  }

  useEffect(() => { loadAll(); loadHealth() }, [])

  // â”€â”€ Pipeline handlers â”€â”€
  const handleSaveApiKey = () => { localStorage.setItem('ids_api_key', apiKey); flash('success', 'API Key saved') }
  const handleStart = async () => {
    try { await startSniffer(snifferConfig); flash('success', 'Pipeline started'); loadAll() }
    catch (err) { flash('error', err.response?.data?.detail || err.message) }
  }
  const handleStop = async () => {
    try { await stopSniffer(); flash('success', 'Pipeline stopped'); loadAll() }
    catch (err) { flash('error', err.response?.data?.detail || err.message) }
  }
  const handleToggleDemo = async (val) => {
    try {
      const resp = await fetch('/api/demo/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: val })
      });
      const data = await resp.json();
      setDemoEnabled(data.enable_demo_replay);
      flash('success', `Demo mode ${val ? 'enabled' : 'disabled'}`);
    } catch (err) { flash('error', 'Failed to update demo config') }
  }

  // â”€â”€ Whitelist handlers â”€â”€
  const handleAddWhitelist = async () => {
    if (!newWlIp) return
    try {
      await addWhitelist({ ip_address: newWlIp, reason: 'Added from dashboard' })
      setNewWlIp('')
      fetchWhitelist().then((r) => setWhitelist(r.data?.items || []))
      flash('success', `${newWlIp} added to whitelist`)
    } catch (err) { flash('error', err.response?.data?.message || err.message) }
  }
  const handleRemoveWhitelist = async (id) => {
    try { await removeWhitelist({ whitelist_id: id }); fetchWhitelist().then((r) => setWhitelist(r.data?.items || [])) }
    catch {}
  }

  // â”€â”€ Blacklist handlers â”€â”€
  const handleAddBlacklist = async () => {
    if (!newBlIp) return
    try {
      await addBlacklist({
        ip_address: newBlIp,
        reason: newBlReason || undefined,
        expires_hours: newBlHours ? parseInt(newBlHours) : undefined,
      })
      setNewBlIp(''); setNewBlReason(''); setNewBlHours('')
      fetchBlacklist().then(setBlacklist)
      flash('success', `${newBlIp} added to blacklist`)
    } catch (err) { flash('error', err.response?.data?.detail || err.message) }
  }
  const handleRemoveBlacklist = async (ip) => {
    try { await removeBlacklist(ip); fetchBlacklist().then(setBlacklist) }
    catch (err) { flash('error', err.response?.data?.detail || err.message) }
  }

  // â”€â”€ Geo-block handlers â”€â”€
  const handleAddGeoBlock = async (code, name) => {
    const cc = (code || newCountryCode).trim().toUpperCase()
    const cn = name || newCountryName
    if (!cc) return
    try {
      await addGeoBlock({ country_code: cc, country_name: cn || undefined })
      setNewCountryCode(''); setNewCountryName('')
      fetchGeoBlocks().then(setGeoRules)
      flash('success', `Geo-block added: ${cc}`)
    } catch (err) { flash('error', err.response?.data?.detail || err.message) }
  }
  const handleRemoveGeoBlock = async (code) => {
    try { await removeGeoBlock(code); fetchGeoBlocks().then(setGeoRules) }
    catch (err) { flash('error', err.response?.data?.detail || err.message) }
  }

  return (
    <div className="p-6 space-y-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900">Settings</h1>

      {message && (
        <div className={`p-3 rounded-lg text-sm ${message.type === 'success' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'}`}>
          {message.text}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200">
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${tab === t ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            {t}
          </button>
        ))}
      </div>

      {/* â”€â”€ PIPELINE TAB â”€â”€ */}
      {tab === 'Pipeline' && (
        <div className="space-y-5">
          {/* API Key */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2"><Key className="w-4 h-4" /> API Key</h3>
            <div className="flex gap-3">
              <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)}
                placeholder="Enter X-API-Key" className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm" />
              <button onClick={handleSaveApiKey} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">Save</button>
            </div>
          </div>

          {/* Demo Mode Toggle */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                <Terminal className="w-4 h-4 text-purple-600" /> Demo Replay Mode
              </h3>
              <label className="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" checked={demoEnabled} 
                  onChange={(e) => handleToggleDemo(e.target.checked)}
                  className="sr-only peer" />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-600"></div>
              </label>
            </div>
            <p className="text-xs text-gray-400 mt-2">
              Bật tính năng này để cho phép chạy mô phỏng các cuộc tấn công CICIDS2017 mà không cần card mạng thật.
            </p>
          </div>

          {/* Service Health */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2"><Wifi className="w-4 h-4" /> Service Health</h3>
              <div className="flex items-center gap-2">
                {healthCheckedAt && <span className="text-xs text-gray-400">Last: {healthCheckedAt}</span>}
                <button onClick={loadHealth} disabled={healthLoading}
                  className="flex items-center gap-1 px-2 py-1 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50">
                  <RefreshCw className={`w-3 h-3 ${healthLoading ? 'animate-spin' : ''}`} /> Refresh
                </button>
              </div>
            </div>
            {health ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[['PostgreSQL', health.postgres?.connected], ['Cache (Mem)', health.cache?.connected], ['ML Model', health.model_loaded]].map(([name, ok]) => (
                  <div key={name} className="flex items-center gap-2 p-2 rounded-lg bg-gray-50">
                    <span className={`w-2.5 h-2.5 rounded-full ${ok ? 'bg-green-500' : 'bg-red-500'}`} />
                    <span className="text-sm text-gray-700">{name}</span>
                  </div>
                ))}
              </div>
            ) : <p className="text-sm text-gray-400">Unable to fetch</p>}
          </div>

          {/* Pipeline Control */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Pipeline Control</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
              <div>
                <label className="text-xs text-gray-500">Interface</label>
                <select value={snifferConfig.interface}
                  onChange={(e) => setSnifferConfig((c) => ({ ...c, interface: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm mt-1 bg-white">
                  {interfaces.length > 0 ? interfaces.map((i) => <option key={i} value={i}>{i}</option>)
                    : <option value={snifferConfig.interface}>{snifferConfig.interface}</option>}
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500">Model</label>
                <input value={snifferConfig.model_name}
                  onChange={(e) => setSnifferConfig((c) => ({ ...c, model_name: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm mt-1" />
              </div>
              <div>
                <label className="text-xs text-gray-500">Min Packets</label>
                <input type="number" value={snifferConfig.min_packets}
                  onChange={(e) => setSnifferConfig((c) => ({ ...c, min_packets: parseInt(e.target.value) || 10 }))}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm mt-1" />
              </div>
            </div>
            <div className="flex gap-3">
              <button onClick={handleStart} disabled={status?.is_running}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 disabled:opacity-50">
                <Play className="w-4 h-4" /> Start
              </button>
              <button onClick={handleStop} disabled={!status?.is_running}
                className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700 disabled:opacity-50">
                <Square className="w-4 h-4" /> Stop
              </button>
            </div>
            {status && (
              <p className="text-xs text-gray-500 mt-3">
                Status: {status.is_running ? 'đŸŸ¢ Running' : 'âª Stopped'} | Packets: {status.processed_packets || 0} | Inferences: {status.inference_runs || 0}
              </p>
            )}
          </div>
        </div>
      )}

      {/* â”€â”€ WHITELIST TAB â”€â”€ */}
      {tab === 'Whitelist' && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
            <Shield className="w-4 h-4 text-green-600" /> IP Whitelist
          </h3>
          <div className="flex gap-3 mb-4">
            <input value={newWlIp} onChange={(e) => setNewWlIp(e.target.value)}
              placeholder="192.168.1.100" className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm" />
            <button onClick={handleAddWhitelist} className="px-4 py-2 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700">Add</button>
          </div>
          {whitelist.length > 0 ? (
            <div className="space-y-2">
              {whitelist.map((item) => (
                <div key={item.id} className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg">
                  <div>
                    <span className="text-sm font-mono">{item.ip_address}</span>
                    {item.reason && <span className="text-xs text-gray-400 ml-2">â€” {item.reason}</span>}
                  </div>
                  <button onClick={() => handleRemoveWhitelist(item.id)} className="text-xs text-red-500 hover:text-red-700">Remove</button>
                </div>
              ))}
            </div>
          ) : <p className="text-sm text-gray-400">No whitelisted IPs</p>}
        </div>
      )}

      {/* â”€â”€ BLACKLIST TAB â”€â”€ */}
      {tab === 'Blacklist' && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
            <Ban className="w-4 h-4 text-red-600" /> IP Blacklist
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
            <input value={newBlIp} onChange={(e) => setNewBlIp(e.target.value)}
              placeholder="IP address *" className="px-3 py-2 border border-gray-200 rounded-lg text-sm" />
            <input value={newBlReason} onChange={(e) => setNewBlReason(e.target.value)}
              placeholder="Reason (optional)" className="px-3 py-2 border border-gray-200 rounded-lg text-sm" />
            <input type="number" value={newBlHours} onChange={(e) => setNewBlHours(e.target.value)}
              placeholder="Expires (hours, blank=permanent)" className="px-3 py-2 border border-gray-200 rounded-lg text-sm" />
            <button onClick={handleAddBlacklist} className="px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700">Block IP</button>
          </div>
          {blacklist.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-100">
                  <tr>
                    <th className="text-left px-3 py-2 text-xs font-medium text-gray-600">IP Address</th>
                    <th className="text-left px-3 py-2 text-xs font-medium text-gray-600">Country</th>
                    <th className="text-left px-3 py-2 text-xs font-medium text-gray-600">Reason</th>
                    <th className="text-left px-3 py-2 text-xs font-medium text-gray-600">Auto</th>
                    <th className="text-left px-3 py-2 text-xs font-medium text-gray-600">Expires</th>
                    <th className="px-3 py-2"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {blacklist.map((item) => (
                    <tr key={item.id}>
                      <td className="px-3 py-2 font-mono text-xs">{item.ip_address}</td>
                      <td className="px-3 py-2 text-xs">{item.country_code || 'â€”'}</td>
                      <td className="px-3 py-2 text-xs text-gray-500">{item.reason || 'â€”'}</td>
                      <td className="px-3 py-2">
                        {item.auto_blocked && <span className="text-xs bg-orange-100 text-orange-700 px-1.5 py-0.5 rounded">Auto</span>}
                      </td>
                      <td className="px-3 py-2 text-xs text-gray-500">
                        {item.expires_at ? formatDatetime(item.expires_at) : 'Permanent'}
                      </td>
                      <td className="px-3 py-2">
                        <button onClick={() => handleRemoveBlacklist(item.ip_address)}
                          className="text-xs text-red-500 hover:text-red-700">Unblock</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="text-sm text-gray-400">No blocked IPs</p>}
        </div>
      )}

      {/* â”€â”€ GEO BLOCK TAB â”€â”€ */}
      {tab === 'Geo Block' && (
        <div className="space-y-4">
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <Globe className="w-4 h-4 text-purple-600" /> Geo Blocking â€” Quick Add
            </h3>
            <div className="flex flex-wrap gap-2 mb-4">
              {COMMON_COUNTRIES.map((c) => {
                const active = geoRules.some((r) => r.country_code === c.code && r.is_active)
                return (
                  <button key={c.code}
                    onClick={() => active ? handleRemoveGeoBlock(c.code) : handleAddGeoBlock(c.code, c.name)}
                    className={`px-3 py-1.5 text-xs rounded-lg border font-medium transition-colors ${active ? 'bg-purple-600 text-white border-purple-600' : 'bg-white text-gray-600 border-gray-200 hover:border-purple-400'}`}>
                    {active ? 'âœ“ ' : ''}{c.code} â€” {c.name}
                  </button>
                )
              })}
            </div>
            <div className="flex gap-3">
              <input value={newCountryCode} onChange={(e) => setNewCountryCode(e.target.value.toUpperCase())}
                placeholder="Country code (e.g. DE)" maxLength={5}
                className="w-36 px-3 py-2 border border-gray-200 rounded-lg text-sm uppercase" />
              <input value={newCountryName} onChange={(e) => setNewCountryName(e.target.value)}
                placeholder="Country name (optional)" className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm" />
              <button onClick={() => handleAddGeoBlock()} className="px-4 py-2 bg-purple-600 text-white text-sm rounded-lg hover:bg-purple-700">Block Country</button>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Active Geo-block Rules ({geoRules.filter(r => r.is_active).length})</h3>
            {geoRules.filter(r => r.is_active).length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {geoRules.filter(r => r.is_active).map((rule) => (
                  <div key={rule.id} className="flex items-center gap-2 px-3 py-1.5 bg-purple-50 border border-purple-200 rounded-lg">
                    <span className="text-sm font-semibold text-purple-700">{rule.country_code}</span>
                    {rule.country_name && <span className="text-xs text-gray-500">{rule.country_name}</span>}
                    <button onClick={() => handleRemoveGeoBlock(rule.country_code)} className="text-purple-400 hover:text-red-500 ml-1">âœ•</button>
                  </div>
                ))}
              </div>
            ) : <p className="text-sm text-gray-400">No geo-block rules active</p>}
          </div>
        </div>
      )}
    </div>
  )
}
