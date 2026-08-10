import { useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { isAuthenticated, setAuth } from '../lib/auth'
import axios from 'axios'

/**
 * Route guard — chỉ cho phép truy cập khi đã đăng nhập.
 *
 * Dùng module-level cache để tránh re-check mỗi lần chuyển tab.
 * Chỉ check /api/auth/me một lần duy nhất khi localStorage trống.
 */

// Cache ở module level — không reset khi component re-render
let _authChecked = false
let _authResult = isAuthenticated()

export default function RequireAuth({ children }) {
  const location = useLocation()

  // Nếu đã check rồi hoặc đã có auth → không cần loading
  const [checking, setChecking] = useState(!_authChecked && !_authResult)
  const [authed, setAuthed] = useState(_authResult)

  useEffect(() => {
    // Đã check rồi hoặc đã có auth → bỏ qua
    if (_authChecked || _authResult) {
      setChecking(false)
      setAuthed(_authResult)
      return
    }

    // localStorage trống → thử dùng cookie để khôi phục session (1 lần duy nhất)
    axios.get('/api/auth/me', { withCredentials: true })
      .then((res) => {
        if (res.data) {
          setAuth(res.data, null)
          _authResult = true
          setAuthed(true)
          // Thông báo cho các component con biết session đã được khôi phục
          window.dispatchEvent(new CustomEvent('auth:restored', { detail: res.data }))
        } else {
          _authResult = false
          setAuthed(false)
        }
      })
      .catch(() => {
        _authResult = false
        setAuthed(false)
      })
      .finally(() => {
        _authChecked = true
        setChecking(false)
      })
  }, [])

  // Reset cache khi logout (localStorage bị xóa)
  useEffect(() => {
    if (!isAuthenticated() && _authResult) {
      _authChecked = false
      _authResult = false
    }
  })

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-slate-500 text-sm">Đang xác thực...</p>
        </div>
      </div>
    )
  }

  if (!authed) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return children
}
