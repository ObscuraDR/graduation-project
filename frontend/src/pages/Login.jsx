import { useState } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import { Shield, Lock, User, Loader2 } from 'lucide-react'
import { loginRequest, fetchMe } from '../lib/api'
import { setAuth } from '../lib/auth'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const navigate = useNavigate()
  const location = useLocation()
  // Sau khi đăng nhập, quay lại trang người dùng định vào (nếu có)
  const from = location.state?.from?.pathname || '/'

  async function handleSubmit(e) {
    e.preventDefault()
    if (!username.trim() || !password) {
      setError('Vui lòng nhập đầy đủ thông tin')
      return
    }

    setError('')
    setLoading(true)
    try {
      const loginResponse = await loginRequest(username.trim(), password)
      const user = await fetchMe()
      setAuth(user, loginResponse.access_token || loginResponse.token)
      navigate(from, { replace: true })
    } catch (err) {
      if (err.response?.status === 403) {
        setError(err.response.data?.detail || 'Tài khoản của bạn đã bị khóa tạm thời.')
      } else if (err.response?.status === 401) {
        setError('Sai tên đăng nhập hoặc mật khẩu')
      } else {
        setError('Không kết nối được tới máy chủ. Kiểm tra backend.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 px-4">
      {/* Background gradient orbs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/3 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/3 w-96 h-96 bg-violet-600/10 rounded-full blur-3xl" />
      </div>

      <div className="w-full max-w-md relative z-10">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-600 to-blue-400 shadow-2xl shadow-blue-500/30 mb-4">
            <Shield className="w-9 h-9 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-slate-100">Z-Sentinel</h1>
          <p className="text-sm text-slate-500 mt-1">IDS Monitoring Dashboard</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-slate-900/80 backdrop-blur-xl rounded-2xl p-8 shadow-2xl border border-slate-800/60 space-y-5"
        >
          <h2 className="text-lg font-semibold text-slate-100">Đăng nhập</h2>

          {error && (
            <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-4 py-2.5 text-sm text-red-400">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-slate-400 mb-1.5">
              Tên đăng nhập
            </label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600" />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
                required
                className="w-full pl-10 pr-3 py-2.5 rounded-lg bg-slate-800/80 border border-slate-700 text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                placeholder="admin"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-400 mb-1.5">
              Mật khẩu
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full pl-10 pr-3 py-2.5 rounded-lg bg-slate-800/80 border border-slate-700 text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                placeholder="••••••••"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-60 disabled:cursor-not-allowed text-white font-medium transition-all shadow-lg shadow-blue-500/20 hover:shadow-blue-500/30"
          >
            {loading && <Loader2 className="w-4 h-4 animate-spin" />}
            {loading ? 'Đang đăng nhập...' : 'Đăng nhập'}
          </button>

          <div className="text-center pt-2">
            <p className="text-sm text-slate-500">
              Chưa có tài khoản?{' '}
              <Link to="/register" className="text-blue-400 hover:text-blue-300 font-medium transition-colors">
                Đăng ký ngay
              </Link>
            </p>
          </div>
        </form>

        <p className="text-center text-xs text-slate-700 mt-6">
          Z-Sentinel IDS v1.0.0
        </p>
      </div>
    </div>
  )
}
