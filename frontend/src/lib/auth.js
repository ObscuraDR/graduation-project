/**
 * Auth helpers — lưu/đọc JWT token và thông tin user trong localStorage.
 *
 * Phạm vi (đồ án): chỉ 1 admin đăng nhập. Token được lưu ở localStorage để
 * giữ phiên qua các lần reload. Đây là cách đơn giản, đủ dùng cho dashboard
 * giám sát nội bộ.
 *
 * NOTE: Dùng lazy HTTP call để logout thay vì static import api.js,
 * tránh circular dependency (api.js → auth.js → api.js).
 */
const USER_KEY = 'ids_user'
const TOKEN_KEY = 'ids_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function getUser() {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function setAuth(user, token) {
  if (user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user))
  }
  if (token) {
    localStorage.setItem(TOKEN_KEY, token)
  }
}

export function clearAuth() {
  localStorage.removeItem(USER_KEY)
  localStorage.removeItem(TOKEN_KEY)
}

export function isAuthenticated() {
  return Boolean(getUser())
}

export async function logout() {
  try {
    // Dùng fetch trực tiếp để tránh circular import với api.js
    await fetch('/api/auth/logout', {
      method: 'POST',
      credentials: 'include',
    })
  } catch (err) {
    console.error('Failed to call logout endpoint', err)
  }
  clearAuth()
  window.location.href = '/login'
}

export function hasRole(requiredRoles = []) {
  const user = getUser()
  if (!user) return false
  return requiredRoles.includes(user.role)
}
