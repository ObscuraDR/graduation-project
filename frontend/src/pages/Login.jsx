import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Shield, Lock, User, Loader2 } from 'lucide-react'
import { loginRequest } from '../lib/api'
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
    setError('')
    setLoading(true)
    try {
      const data = await loginRequest(username.trim(), password)
      setAuth(data.access_token, data.user)
      navigate(from, { replace: true })
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Sai tên đăng nhập hoặc mật khẩu')
      } else {
        setError('Không kết nối được tới máy chủ. Kiểm tra backend.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-900 px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-blue-600/20 mb-4">
            <Shield className="w-9 h-9 text-blue-400" />
          </div>
          <h1 className="text-2xl font-bold text-white">Z-Sentinel</h1>
          <p className="text-sm text-gray-400 mt-1">IDS Monitoring Dashboard</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-gray-800 rounded-2xl p-8 shadow-xl border border-gray-700 space-y-5"
        >
          <h2 className="text-lg font-semibold text-white">Đăng nhập</h2>

          {error && (
            <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-4 py-2.5 text-sm text-red-300">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              Tên đăng nhập
            </label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
                required
                className="w-full pl-10 pr-3 py-2.5 rounded-lg bg-gray-900 border border-gray-600 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="admin"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              Mật khẩu
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full pl-10 pr-3 py-2.5 rounded-lg bg-gray-900 border border-gray-600 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="••••••••"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-60 disabled:cursor-not-allowed text-white font-medium transition-colors"
          >
            {loading && <Loader2 className="w-4 h-4 animate-spin" />}
            {loading ? 'Đang đăng nhập...' : 'Đăng nhập'}
          </button>
        </form>

        <p className="text-center text-xs text-gray-600 mt-6">
          Z-Sentinel IDS v1.0.0
        </p>
      </div>
    </div>
  )
}
