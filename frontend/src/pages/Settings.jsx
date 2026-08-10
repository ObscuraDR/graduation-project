import { useEffect, useState } from 'react'
import { Play, Square, Key, Wifi, RefreshCw, Shield, Globe, Ban, Terminal, Plus, Check, X } from 'lucide-react'
import {
  fetchSnifferStatus, startSniffer, stopSniffer, fetchHealthDetailed,
  fetchWhitelist, addWhitelist, removeWhitelist, fetchInterfaces,
  fetchBlacklist, addBlacklist, removeBlacklist,
  fetchGeoBlocks, addGeoBlock, removeGeoBlock,
} from '../lib/api'
import { formatDatetime } from '../lib/datetime'
import BlockIPModal from '../components/BlockIPModal'

const TABS = ['Whitelist', 'Blacklist', 'Geo Block']

// Common country codes for quick-add
const COMMON_COUNTRIES = [
  { code: 'CN', name: 'China' }, { code: 'RU', name: 'Russia' },
  { code: 'KP', name: 'North Korea' }, { code: 'IR', name: 'Iran' },
  { code: 'VN', name: 'Vietnam' }, { code: 'US', name: 'United States' },
]

export default function Settings() {
  const [tab, setTab] = useState('Whitelist')
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
  const [showBlockIPModal, setShowBlockIPModal] = useState(false)

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
    fetch('/api/demo/status').then(r => r.json()).then(data => {
      setDemoEnabled(data.running === true)
    }).catch(() => {})
  }

  const loadHealth = async () => {
    setHealthLoading(true)
    try {
      const d = await fetchHealthDetailed()
      setHealth(d)
      setHealthCheckedAt(new Date().toLocaleTimeString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' }))
    } catch {}
    setHealthLoading(false)
  }

  useEffect(() => { loadAll(); loadHealth() }, [])

  // Pipeline handlers
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

  // Whitelist handlers
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

  // Blacklist handlers
  const handleAddBlacklist = async (data) => {
    try {
      await addBlacklist(data)
      fetchBlacklist().then(setBlacklist)
      flash('success', `${data.ip_address} added to blacklist`)
      setShowBlockIPModal(false)
    } catch (err) { flash('error', err.response?.data?.detail || err.message) }
  }
  const handleRemoveBlacklist = async (ip) => {
    try { await removeBlacklist(ip); fetchBlacklist().then(setBlacklist) }
    catch (err) { flash('error', err.response?.data?.detail || err.message) }
  }

  // Geo-block handlers
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

  const inputClass = "w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 text-sm focus:outline-none focus:border-blue-500 transition-colors"

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-slate-100">Cài đặt Nâng cao</h1>

      {message && (
        <div className={`p-3 rounded-lg text-sm flex items-center gap-2 border ${
          message.type === 'success' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' : 'bg-red-500/10 text-red-400 border-red-500/30'
        }`}>
          {message.text}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-800 pb-1">
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-all rounded-t-lg ${
              tab === t
                ? 'border-blue-500 text-blue-400 bg-blue-500/10'
                : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
            }`}>
            {t}
          </button>
        ))}
      </div>

      {/* Whitelist Tab */}
      {tab === 'Whitelist' && (
        <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 p-5 space-y-4">
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
            <Shield className="w-4 h-4 text-emerald-400" /> Danh sách Whitelist (IP Tin tưởng)
          </h3>
          <div className="flex gap-3">
            <input value={newWlIp} onChange={(e) => setNewWlIp(e.target.value)}
              placeholder="Nhập IP (ví dụ: 192.168.1.100)" className={inputClass} />
            <button onClick={handleAddWhitelist} className="px-4 py-2 bg-emerald-600 text-white text-sm rounded-lg hover:bg-emerald-500 transition-colors font-medium shrink-0">Thêm</button>
          </div>
          {whitelist.length > 0 ? (
            <div className="space-y-2">
              {whitelist.map((item) => (
                <div key={item.id} className="flex items-center justify-between py-2.5 px-4 bg-slate-800/40 border border-slate-800 rounded-lg">
                  <div>
                    <span className="text-sm font-mono text-slate-200">{item.ip_address}</span>
                    {item.reason && <span className="text-xs text-slate-500 ml-3">— {item.reason}</span>}
                  </div>
                  <button onClick={() => handleRemoveWhitelist(item.id)} className="text-xs text-red-400 hover:text-red-300 transition-colors">Xóa</button>
                </div>
              ))}
            </div>
          ) : <p className="text-sm text-slate-500">Chưa có địa chỉ IP nào trong danh sách Whitelist.</p>}
        </div>
      )}

      {/* Blacklist Tab */}
      {tab === 'Blacklist' && (
        <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <Ban className="w-4 h-4 text-red-400" /> Danh sách Blacklist (IP Bị chặn)
            </h3>
            <button
              onClick={() => setShowBlockIPModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-sm rounded-lg transition-colors font-medium shadow-lg shadow-red-500/20"
            >
              <Plus className="w-4 h-4" /> Chặn IP Mới
            </button>
          </div>
          {blacklist.length > 0 ? (
            <div className="overflow-x-auto rounded-lg border border-slate-800">
              <table className="w-full text-sm">
                <thead className="bg-slate-800/60 text-slate-400 border-b border-slate-800">
                  <tr>
                    <th className="text-left px-3 py-2.5 text-xs font-semibold">IP Address</th>
                    <th className="text-left px-3 py-2.5 text-xs font-semibold">Quốc gia</th>
                    <th className="text-left px-3 py-2.5 text-xs font-semibold">Lý do</th>
                    <th className="text-left px-3 py-2.5 text-xs font-semibold">Loại</th>
                    <th className="text-left px-3 py-2.5 text-xs font-semibold">Hết hạn</th>
                    <th className="px-3 py-2.5"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-300">
                  {blacklist.map((item) => (
                    <tr key={item.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="px-3 py-2.5 font-mono text-xs text-slate-200">{item.ip_address}</td>
                      <td className="px-3 py-2.5 text-xs">{item.country_code || '—'}</td>
                      <td className="px-3 py-2.5 text-xs text-slate-400">{item.reason || '—'}</td>
                      <td className="px-3 py-2.5">
                        {item.auto_blocked && <span className="text-xs bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2 py-0.5 rounded-full font-medium">Tự động</span>}
                      </td>
                      <td className="px-3 py-2.5 text-xs text-slate-400">
                        {item.expires_at ? formatDatetime(item.expires_at) : 'Vĩnh viễn'}
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        <button onClick={() => handleRemoveBlacklist(item.ip_address)}
                          className="text-xs text-red-400 hover:text-red-300 transition-colors">Gỡ chặn</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="text-sm text-slate-500">Chưa có IP nào trong danh sách Blacklist.</p>}
        </div>
      )}

      {/* Geo Block Tab */}
      {tab === 'Geo Block' && (
        <div className="space-y-4">
          <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 p-5 space-y-4">
            <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <Globe className="w-4 h-4 text-violet-400" /> Chặn theo Quốc gia — Chọn nhanh
            </h3>
            <div className="flex flex-wrap gap-2">
              {COMMON_COUNTRIES.map((c) => {
                const active = geoRules.some((r) => r.country_code === c.code && r.is_active)
                return (
                  <button key={c.code}
                    onClick={() => active ? handleRemoveGeoBlock(c.code) : handleAddGeoBlock(c.code, c.name)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border font-medium transition-all ${
                      active
                        ? 'bg-violet-600 text-white border-violet-500 shadow-sm shadow-violet-500/20'
                        : 'bg-slate-800/60 text-slate-400 border-slate-700 hover:border-violet-500/50 hover:text-slate-200'
                    }`}>
                    {active ? <Check className="w-3 h-3 text-white" /> : null}
                    {c.code} — {c.name}
                  </button>
                )
              })}
            </div>
            <div className="flex gap-3 pt-2">
              <input value={newCountryCode} onChange={(e) => setNewCountryCode(e.target.value.toUpperCase())}
                placeholder="Mã (VD: DE)" maxLength={5}
                className="w-32 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 text-sm uppercase focus:outline-none focus:border-violet-500" />
              <input value={newCountryName} onChange={(e) => setNewCountryName(e.target.value)}
                placeholder="Tên quốc gia (tùy chọn)" className={inputClass} />
              <button onClick={() => handleAddGeoBlock()} className="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white text-sm rounded-lg transition-colors font-medium shrink-0">Chặn Quốc gia</button>
            </div>
          </div>

          <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 p-5 space-y-3">
            <h3 className="text-sm font-semibold text-slate-200">Quốc gia đang chặn ({geoRules.filter(r => r.is_active).length})</h3>
            {geoRules.filter(r => r.is_active).length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {geoRules.filter(r => r.is_active).map((rule) => (
                  <div key={rule.id} className="flex items-center gap-2 px-3 py-1.5 bg-violet-500/10 border border-violet-500/30 rounded-lg text-slate-200">
                    <span className="text-sm font-semibold text-violet-400">{rule.country_code}</span>
                    {rule.country_name && <span className="text-xs text-slate-400">{rule.country_name}</span>}
                    <button onClick={() => handleRemoveGeoBlock(rule.country_code)} className="text-slate-400 hover:text-red-400 ml-1 transition-colors">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            ) : <p className="text-sm text-slate-500">Chưa chặn quốc gia nào.</p>}
          </div>
        </div>
      )}
      
      {/* Block IP Modal */}
      <BlockIPModal
        isOpen={showBlockIPModal}
        onClose={() => setShowBlockIPModal(false)}
        onBlock={handleAddBlacklist}
      />
    </div>
  )
}
