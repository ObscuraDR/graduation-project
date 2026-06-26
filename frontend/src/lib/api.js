import axios from 'axios'
import { clearAuth } from './auth'
const API_BASE = '/api'

function getApiKey() {
  return localStorage.getItem('ids_api_key') || ''
}

const api = axios.create({
  baseURL: API_BASE,
  timeout: 15000, // tăng từ 10s lên 15s cho các query nặng
})

// Crucial for sending/receiving cookies with cross-origin requests
axios.defaults.withCredentials = true;
api.defaults.withCredentials = true;

// Helper to get a cookie by name
function getCookie(name) {
  const nameEQ = name + "=";
  const ca = document.cookie.split(';');
  for(let i=0; i < ca.length; i++) {
    let c = ca[i];
    while (c.charAt(0) === ' ') c = c.substring(1, c.length);
    if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
  }
  return null;
}

// Tự động thêm X-API-Key + Bearer token cho mọi request
api.interceptors.request.use((config) => {
  const key = getApiKey()
  if (key) config.headers['X-API-Key'] = key
  // JWT is now in HttpOnly cookie, browser handles it automatically.
  // Add CSRF token for state-changing methods (POST, PUT, DELETE, PATCH)
  const csrfToken = getCookie('csrf_token');
  if (csrfToken && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(config.method.toUpperCase())) {
    config.headers['X-CSRF-Token'] = csrfToken;
  }
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

export async function fetchInterfaces() {
  const res = await api.get('/sniffer/interfaces')
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
export async function fetchAlerts({ skip = 0, limit = 50, severity, status, attackType } = {}) {
  const params = { skip, limit }
  if (severity) params.severity = severity
  if (status) params.status = status
  if (attackType) params.attackType = attackType
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

export async function fetchDashboardStats(hours = 24) {
  const res = await api.get('/stats/dashboard', { params: { hours } })
  return res.data
}

export async function fetchSecurityLogs(params = {}) {
  const res = await api.get('/logs/', { params })
  return res.data
}

export async function fetchAuditLogs(params = {}) {
  const res = await api.get('/audit/', { params })
  return res.data
}

export async function fetchBlockHistory(limit = 100, ipAddress = null) {
  const params = { limit }
  if (ipAddress) params.ip_address = ipAddress
  const res = await api.get('/blacklist/history', { params })
  return res.data
}

export async function lookupGeoIP(ip) {
  const res = await api.get(`/geoip/lookup/${encodeURIComponent(ip)}`)
  return res.data
}

export async function fetchGeoAllow() {
  const res = await api.get('/geoallow/')
  return res.data
}

export async function addGeoAllow(data) {
  const res = await api.post('/geoallow/', data)
  return res.data
}

export async function removeGeoAllow(countryCode) {
  const res = await api.delete(`/geoallow/${countryCode}`)
  return res.data
}

export async function fetchGeoWatch() {
  const res = await api.get('/geowatch/')
  return res.data
}

export async function addGeoWatch(data) {
  const res = await api.post('/geowatch/', data)
  return res.data
}

export async function removeGeoWatch(countryCode) {
  const res = await api.delete(`/geowatch/${countryCode}`)
  return res.data
}

export async function addBlacklistWithDuration(ip, reason, expiresHours) {
  const res = await api.post('/blacklist/', {
    ip_address: ip,
    reason,
    expires_hours: expiresHours,
  })
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

// ─── Blacklist ────────────────────────────────────────────────────────────────
export async function fetchBlacklist() {
  const res = await api.get('/blacklist/')
  return res.data
}

export async function addBlacklist(data) {
  const res = await api.post('/blacklist/', data)
  return res.data
}

export async function removeBlacklist(ipAddress) {
  const res = await api.delete(`/blacklist/${ipAddress}`)
  return res.data
}

export async function fetchCloudflareBlacklist() {
  const res = await api.get('/firewall/cloudflare-blacklist')
  return res.data
}

export async function removeCloudflareBlacklist(ip) {
  const res = await api.delete(`/firewall/cloudflare-unblock/${ip}`)
  return res.data
}

// ─── Geo-block ────────────────────────────────────────────────────────────────
export async function fetchGeoBlocks() {
  const res = await api.get('/geoblock/')
  return res.data
}

export async function addGeoBlock(data) {
  const res = await api.post('/geoblock/', data)
  return res.data
}

export async function removeGeoBlock(countryCode) {
  const res = await api.delete(`/geoblock/${countryCode}`)
  return res.data
}

// ─── Reports ──────────────────────────────────────────────────────────────────
export async function fetchSecurityReport(hours = 24, save = false) {
  const res = await api.get('/reports/security', { params: { hours, save } })
  return res.data
}

export async function fetchReportHistory(limit = 10) {
  const res = await api.get('/reports/security/history', { params: { limit } })
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
  const res = await axios.post(`${API_BASE}/auth/login`, { username, password }, { withCredentials: true })
  return res.data
}

export async function logoutRequest() {
  const res = await api.post('/auth/logout')
  return res.data
}

export async function fetchMe() {
  const res = await api.get('/auth/me')
  return res.data
}

export default api
