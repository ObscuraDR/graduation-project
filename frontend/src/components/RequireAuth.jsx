import { useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { isAuthenticated, setAuth } from '../lib/auth'
import axios from 'axios'

/**
 * Route guard — chỉ cho phép truy cập khi đã đăng nhập.
 *
 * Thay vì redirect ngay khi localStorage trống (có thể do clearAuth() nhầm),
 * component thử gọi /api/auth/me để kiểm tra cookie HttpOnly còn sống không.
 * Chỉ redirect về /login khi cả localStorage lẫn cookie đều không hợp lệ.
 */
export default function RequireAuth({ children }) {
  const location = useLocation()
  const [checking, setChecking] = useState(!isAuthenticated())
  const [authed, setAuthed] = useState(isAuthenticated())

  useEffect(() => {
    // Nếu đã có user trong localStorage thì không cần check lại
    if (isAuthenticated()) {
      setAuthed(true)
      setChecking(false)
      return
    }

    // localStorage trống → thử dùng cookie để khôi phục session
    axios.get('/api/auth/me', { withCredentials: true })
      .then((res) => {
        if (res.data) {
          setAuth(res.data, null)  // restore user vào localStorage
          setAuthed(true)
        } else {
          setAuthed(false)
        }
      })
      .catch(() => {
        setAuthed(false)
      })
      .finally(() => {
        setChecking(false)
      })
  }, [])

  // Đang kiểm tra session → hiển thị màn hình loading thay vì redirect
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
