/**
 * Auth helpers — lưu/đọc JWT token và thông tin user trong localStorage.
 *
 * Phạm vi (đồ án): chỉ 1 admin đăng nhập. Token được lưu ở localStorage để
 * giữ phiên qua các lần reload. Đây là cách đơn giản, đủ dùng cho dashboard
 * giám sát nội bộ.
 */
const USER_KEY = 'ids_user'

// Note: getToken() is no longer needed for API headers 
// as the browser handles the HttpOnly cookie automatically.
export function getToken() {
  return ''; 
}

export function getUser() {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function setAuth(user) {
  if (user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user))
  }
}

export function clearAuth() {
  localStorage.removeItem(USER_KEY)
}

export function isAuthenticated() {
  // Since JWT is in HttpOnly cookie, JS cannot access it.
  // We use the presence of the user object as a proxy for session status.
  return Boolean(getUser())
}

export async function logout() {
  try {
    // Import logoutRequest từ api.js
    const { logoutRequest } = await import('./api'); 
    await logoutRequest();
  } catch (err) {
    console.error("Failed to call logout endpoint", err)
  }
  clearAuth()
  window.location.href = '/login'
}

export function hasRole(requiredRoles = []) {
  const user = getUser()
  if (!user) return false
  return requiredRoles.includes(user.role)
}
