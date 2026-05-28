import axios from 'axios'

const API_BASE = '/api'

// Lấy API key từ localStorage hoặc dùng default
function getApiKey() {
  return localStorage.getItem('ids_api_key') || ''
}

const api = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
})

// Tự động thêm X-API-Key header cho mọi request
api.interceptors.request.use((config) => {
  const key = getApiKey()
  if (key) {
    config.headers['X-API-Key'] = key
  }
  return config
})

// ─── Health ──────────────────────────────────────────────────────────────────
export async function fetchHealth() {
  const res = await axios.get('/health')
  return res.data
}

export async function fetchHealthDetailed() {
  const res = await axios.get('/health/detailed')
  return res.data
}

// ─── Sniffer ─────────────────────────────────────────────────────────────────
export async function startSniffer(params = {}) {
  const res = await api.post('/sniffer/start', null, { params })
  return res.data
}

export async function stopSniffer() {
  const res = await api.post('/sniffer/stop')
  return res.data
}

export async function fetchSnifferStatus() {
  const res = await api.get('/sniffer/status')
  return res.data
}

// ─── Traffic ─────────────────────────────────────────────────────────────────
export async function fetchTrafficStats() {
  const res = await axios.get(`${API_BASE}/traffic/stats`)
  return res.data
}

export async function fetchActiveFlows(limit = 100) {
  const res = await axios.get(`${API_BASE}/traffic/flows`, { params: { limit } })
  return res.data
}

export async function fetchTopTalkers(limit = 10) {
  const res = await axios.get(`${API_BASE}/traffic/top-talkers`, { params: { limit } })
  return res.data
}

// ─── Alerts ──────────────────────────────────────────────────────────────────
export async function fetchAlerts({ skip = 0, limit = 50, severity, status } = {}) {
  const params = { skip, limit }
  if (severity) params.severity = severity
  if (status) params.status = status
  const res = await axios.get(`${API_BASE}/alerts/`, { params })
  return res.data
}

export async function resolveAlert(alertId, notes = '') {
  const res = await axios.put(`${API_BASE}/alerts/${alertId}/resolve`, null, { params: { notes } })
  return res.data
}

export async function deleteAlert(alertId) {
  const res = await axios.delete(`${API_BASE}/alerts/${alertId}`)
  return res.data
}

// ─── Stats ───────────────────────────────────────────────────────────────────
export async function fetchAlertEngineStats() {
  const res = await axios.get(`${API_BASE}/stats/alert-engine`)
  return res.data
}

export async function fetchSystemStats() {
  const res = await axios.get(`${API_BASE}/stats/system`)
  return res.data
}

export async function fetchTrainingReport() {
  const res = await axios.get(`${API_BASE}/stats/training-report`)
  return res.data
}

// ─── Whitelist ───────────────────────────────────────────────────────────────
export async function fetchWhitelist() {
  const res = await axios.get(`${API_BASE}/whitelist/list`)
  return res.data
}

export async function addWhitelist(data) {
  const res = await api.post('/whitelist/add', data)
  return res.data
}

export async function removeWhitelist(data) {
  const res = await api.post('/whitelist/remove', data)
  return res.data
}

// ─── XAI ─────────────────────────────────────────────────────────────────────
export async function explainPrediction(features, modelName = 'ensemble') {
  const res = await axios.post(`${API_BASE}/xai/explain`, { model_name: modelName, features })
  return res.data
}

export default api
