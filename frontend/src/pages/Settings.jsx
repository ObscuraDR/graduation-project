import { useEffect, useState } from 'react'
import { Play, Square, Key, Wifi, RefreshCw, Shield, Ban } from 'lucide-react'
import {
  fetchSnifferStatus, startSniffer, stopSniffer, fetchHealthDetailed,
  fetchWhitelist, addWhitelist, removeWhitelist, fetchInterfaces,
  fetchBlacklist, addBlacklist, removeBlacklist,
} from '../lib/api'
import { hasRole } from '../lib/auth'

const TABS = ['Pipeline', 'Whitelist', 'Blacklist', 'Geo Block']

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

  // Whitelist
  const [whitelist, setWhitelist] = useState([])
  const [newWlIp, setNewWlIp] = useState('')

  // Blacklist
  const [blacklist, setBlacklist] = useState([])
  const [newBlIp, setNewBlIp] = useState('')
  const [newBlReason, setNewBlReason] = useState('')
  const [newBlHours, setNewBlHours] = useState('')

  const flash = (type, text) => {
    setMessage({ type, text })
    setTimeout(() => setMessage(null), 3500)
  }

  const loadAll = () => {
    fetchSnifferStatus().then(setStatus).catch(() => setStatus(null))
    fetchWhitelist().then((r) => setWhitelist(r.data?.items || [])).catch(() => {})
