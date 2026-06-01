import axios from 'axios'
import { getToken, clearAuth } from './auth'

const API_BASE = '/api'

function getApiKey() {
  return localStorage.getItem('ids_api_key') || ''
}

const api = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
})

// Tự động thêm X-API-Key + Bearer token cho mọi request
api.interceptors.request.use((config) => {
  const key = getApiKey()
  if (key) config.headers['X-API-Key'] = key
  const token = getToken()
  if (token) config.headers['Authorization'] = `Bearer ${token}`
  return config
})

// Chỉ logout khi JWT không hợp lệ, không logout khi thiếu API key
api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      const detail = error.response?.data?.detail || ''
      const isApiKeyError = detail.toLowerCase().includes('api key')
      if (!isApiKeyError) {
        clearAuth()
        if (window.location.pathname !== '/login') {
          window.location.assign('/login')
        }
      }
    }
    return Promise.reject(error)
  }
)

// ─── Health ──────────────────────────────────────────────────────────────────
export async function fetchHealth() {
  const res = await api.get('/health')
  return res.data
}

export async function fetchHealthDetailed() {
  const res = await api.get('/health/detailed')
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
  const res = await api.get('/traffic/stats')
  return res.data
}

export async function fetchActiveFlows(limit = 100) {
  const res = await api.get('/traffic/flows', { params: { limit } })
  return res.data
}

export async function fetchTopTalkers(limit = 10) {
  const res = await api.get('/traffic/top-talkers', { params: { limit } })
  return res.data
}

// ─── Alerts ──────────────────────────────────────────────────────────────────
export async function fetchAlerts({ skip = 0, limit = 50, severity, status } = {}) {
  const params = { skip, limit }
  if (severity) params.severity = severity
  if (status) params.status = status
  const res = await api.get('/alerts/', { params })
  return res.data
}

export async function resolveAlert(alertId, notes = '') {
  const res = await api.put(`/alerts/${alertId}/resolve`, null, { params: { notes } })
  return res.data
}

export async function deleteAlert(alertId) {
  const res = await api.delete(`/alerts/${alertId}`)
  return res.data
}

// ─── Stats ───────────────────────────────────────────────────────────────────
export async function fetchAlertEngineStats() {
  const res = await api.get('/stats/alert-engine')
  return res.data
}

export async function fetchSystemStats() {
  const res = await api.get('/stats/system')
  return res.data
}

export async function fetchTrainingReport() {
  const res = await api.get('/stats/training-report')
  return res.data
}

// ─── Whitelist ───────────────────────────────────────────────────────────────
export async function fetchWhitelist() {
  const res = await api.get('/whitelist/list')
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
  const res = await api.post('/xai/explain', { model_name: modelName, features })
  return res.data
}

// ─── Auth (JWT) ──────────────────────────────────────────────────────────────
export async function loginRequest(username, password) {
  // Dùng axios trực tiếp để không vướng interceptor 401-redirect khi đăng nhập sai
  const res = await axios.post(`${API_BASE}/auth/login`, { username, password })
  return res.data
}

export async function fetchMe() {
  const res = await api.get('/auth/me')
  return res.data
}

export default api
