/**
 * Auth helpers — lưu/đọc JWT token và thông tin user trong localStorage.
 *
 * Phạm vi (đồ án): chỉ 1 admin đăng nhập. Token được lưu ở localStorage để
 * giữ phiên qua các lần reload. Đây là cách đơn giản, đủ dùng cho dashboard
 * giám sát nội bộ.
 */

const TOKEN_KEY = 'ids_jwt_token'
const USER_KEY = 'ids_user'

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

export function setAuth(token, user) {
  localStorage.setItem(TOKEN_KEY, token)
  if (user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user))
  }
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function isAuthenticated() {
  return Boolean(getToken())
}
