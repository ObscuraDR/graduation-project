import { Navigate, useLocation } from 'react-router-dom'
import { isAuthenticated } from '../lib/auth'

/**
 * Route guard — chỉ cho phép truy cập khi đã đăng nhập.
 * Nếu chưa có token, chuyển hướng về /login và ghi nhớ trang định vào.
 */
export default function RequireAuth({ children }) {
  const location = useLocation()

  if (!isAuthenticated()) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return children
}
