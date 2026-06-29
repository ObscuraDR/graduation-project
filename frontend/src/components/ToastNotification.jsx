/**
 * ToastNotification — Thông báo nổi real-time khi phát hiện tấn công.
 *
 * Logic thông minh:
 * - ≤ 3 alerts đang chờ → hiển thị từng toast riêng lẻ
 * - > 3 alerts → gộp thành 1 toast tóm tắt để tránh lag
 * - Mỗi toast tự đóng sau 5 giây
 * - Click vào toast → mở AlertDetailModal
 * - Stack tối đa 3 toasts cùng lúc
 */

import { useEffect, useRef, useState } from 'react'
import { X, AlertTriangle, ShieldAlert, ChevronRight } from 'lucide-react'
import SeverityBadge from './SeverityBadge'
import AlertDetailModal from './AlertDetailModal'

// Màu border trái theo severity
const SEVERITY_STYLE = {
  critical: { border: 'border-l-red-500',    bg: 'bg-red-50',     icon: '🔴', text: 'text-red-700' },
  high:     { border: 'border-l-orange-400', bg: 'bg-orange-50',  icon: '🟠', text: 'text-orange-700' },
  medium:   { border: 'border-l-blue-400',   bg: 'bg-blue-50',    icon: '🔵', text: 'text-blue-700' },
  low:      { border: 'border-l-green-400',  bg: 'bg-green-50',   icon: '🟢', text: 'text-green-700' },
  default:  { border: 'border-l-gray-400',   bg: 'bg-gray-50',    icon: '⚪', text: 'text-gray-700' },
}

const TOAST_DURATION = 5000 // 5 giây
const MAX_VISIBLE    = 3    // tối đa 3 toasts cùng lúc
const BATCH_THRESHOLD = 3   // > 3 alerts → gộp thành batch

// ── Single Alert Toast ────────────────────────────────────────────────────────
function SingleToast({ toast, onClose, onViewDetail }) {
  const style = SEVERITY_STYLE[toast.severity] || SEVERITY_STYLE.default
  const [progress, setProgress] = useState(100)
  const intervalRef = useRef(null)

  useEffect(() => {
    const step = 100 / (TOAST_DURATION / 50) // update mỗi 50ms
    intervalRef.current = setInterval(() => {
      setProgress((p) => {
        if (p <= 0) { clearInterval(intervalRef.current); return 0 }
        return p - step
      })
    }, 50)
    const timer = setTimeout(() => onClose(toast.id), TOAST_DURATION)
    return () => { clearInterval(intervalRef.current); clearTimeout(timer) }
  }, [])

  return (
    <div
      className={`
        relative w-80 rounded-xl shadow-lg border border-gray-200
        border-l-4 ${style.border} ${style.bg}
        animate-slide-in overflow-hidden
        transition-all duration-300
      `}
    >
      {/* Progress bar */}
      <div className="absolute top-0 left-0 h-0.5 bg-gray-200 w-full">
        <div
          className={`h-full transition-none ${style.border.replace('border-l-', 'bg-')}`}
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="p-4 pt-5">
        {/* Header */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex items-center gap-2 min-w-0">
            <ShieldAlert className="w-4 h-4 shrink-0 text-gray-500" />
            <span className={`text-sm font-bold truncate ${style.text}`}>
              {style.icon} {toast.severity?.toUpperCase()} — {toast.attack_type}
            </span>
          </div>
          <button
            onClick={() => onClose(toast.id)}
            className="text-gray-400 hover:text-gray-600 shrink-0 mt-0.5"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Info */}
        <p className="text-xs text-gray-600 mb-1 font-mono">
          {toast.src_ip || toast.source_ip}
        </p>
        <p className="text-xs text-gray-400 mb-3">
          Confidence: <span className="font-semibold text-gray-600">
            {Math.round((toast.confidence || 0) * 100)}%
          </span>
        </p>

        {/* Action */}
        <button
          onClick={() => onViewDetail(toast)}
          className={`
            flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-lg
            ${style.text} bg-white border border-gray-200
            hover:shadow-sm transition-all
          `}
        >
          Xem chi tiết <ChevronRight className="w-3 h-3" />
        </button>
      </div>
    </div>
  )
}

// ── Batch Toast (nhiều alerts cùng lúc) ───────────────────────────────────────
function BatchToast({ toast, onClose, onViewAll }) {
  const [progress, setProgress] = useState(100)

  useEffect(() => {
    const step = 100 / (TOAST_DURATION / 50)
    const interval = setInterval(() => {
      setProgress((p) => (p <= 0 ? 0 : p - step))
    }, 50)
    const timer = setTimeout(() => onClose(toast.id), TOAST_DURATION)
    return () => { clearInterval(interval); clearTimeout(timer) }
  }, [])

  const { counts } = toast
  const hasCritical = (counts?.critical || 0) > 0

  return (
    <div className={`
      relative w-80 rounded-xl shadow-lg border border-gray-200
      border-l-4 ${hasCritical ? 'border-l-red-500 bg-red-50' : 'border-l-orange-400 bg-orange-50'}
      animate-slide-in overflow-hidden
    `}>
      {/* Progress bar */}
      <div className="absolute top-0 left-0 h-0.5 bg-gray-200 w-full">
        <div
          className={`h-full transition-none ${hasCritical ? 'bg-red-500' : 'bg-orange-400'}`}
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="p-4 pt-5">
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex items-center gap-2">
            <AlertTriangle className={`w-4 h-4 shrink-0 ${hasCritical ? 'text-red-500' : 'text-orange-400'}`} />
            <span className={`text-sm font-bold ${hasCritical ? 'text-red-700' : 'text-orange-700'}`}>
              {toast.total} cuộc tấn công mới
            </span>
          </div>
          <button onClick={() => onClose(toast.id)} className="text-gray-400 hover:text-gray-600">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Severity breakdown */}
        <div className="flex gap-2 flex-wrap mb-3">
          {counts?.critical > 0 && (
            <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-medium">
              {counts.critical} Critical
            </span>
          )}
          {counts?.high > 0 && (
            <span className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full font-medium">
              {counts.high} High
            </span>
          )}
          {counts?.medium > 0 && (
            <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-medium">
              {counts.medium} Medium
            </span>
          )}
          {counts?.low > 0 && (
            <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
              {counts.low} Low
            </span>
          )}
        </div>

        <button
          onClick={onViewAll}
          className="flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-lg bg-white border border-gray-200 text-gray-700 hover:shadow-sm transition-all"
        >
          Xem tất cả cảnh báo <ChevronRight className="w-3 h-3" />
        </button>
      </div>
    </div>
  )
}

// ── Main ToastContainer ────────────────────────────────────────────────────────
export default function ToastContainer({ alerts }) {
  const [toasts, setToasts] = useState([])
  const [detailAlert, setDetailAlert] = useState(null)
  const queueRef = useRef([])
  const processingRef = useRef(false)

  // Xử lý alerts mới từ WebSocket
  useEffect(() => {
    if (!alerts || alerts.length === 0) return

    // Thêm alerts mới vào queue
    const newAlerts = alerts.filter(
      (a) => !queueRef.current.find((q) => q.id === a.alert_id)
    )
    if (newAlerts.length === 0) return

    queueRef.current = [...queueRef.current, ...newAlerts.map((a) => ({ ...a, id: a.alert_id || Date.now() + Math.random() }))]
    processQueue()
  }, [alerts])

  const processQueue = () => {
    if (processingRef.current) return
    processingRef.current = true

    setToasts((prev) => {
      const pending = queueRef.current
      if (pending.length === 0) { processingRef.current = false; return prev }

      // Giới hạn visible toasts
      const currentCount = prev.filter((t) => !t.isBatch || t.isBatch).length
      if (currentCount >= MAX_VISIBLE) { processingRef.current = false; return prev }

      let newToasts = []

      if (pending.length > BATCH_THRESHOLD) {
        // Gộp thành batch toast
        const counts = pending.reduce((acc, a) => {
          const sev = a.severity || 'low'
          acc[sev] = (acc[sev] || 0) + 1
          return acc
        }, {})
        newToasts = [{
          id: `batch-${Date.now()}`,
          isBatch: true,
          total: pending.length,
          counts,
        }]
        queueRef.current = []
      } else {
        // Hiển thị từng toast, ưu tiên severity cao nhất
        const sorted = [...pending].sort(
          (a, b) => (a.severity === 'critical' ? -1 : b.severity === 'critical' ? 1 : 0)
        )
        const toShow = sorted.slice(0, MAX_VISIBLE - currentCount)
        newToasts = toShow.map((a) => ({ ...a, isBatch: false }))
        queueRef.current = sorted.slice(toShow.length)
      }

      processingRef.current = false
      return [...prev, ...newToasts].slice(-MAX_VISIBLE)
    })
  }

  const closeToast = (id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
    // Sau khi đóng, thử process queue nếu còn
    setTimeout(processQueue, 100)
  }

  const handleViewDetail = (alert) => {
    // Map từ WebSocket format sang AlertDetailModal format
    setDetailAlert({
      alert_id:    alert.alert_id || alert.id,
      attack_type: alert.attack_type,
      source_ip:   alert.src_ip || alert.source_ip,
      dest_ip:     alert.dst_ip || alert.dest_ip,
      source_port: alert.src_port || alert.source_port,
      dest_port:   alert.dst_port || alert.dest_port,
      protocol:    alert.protocol,
      severity:    alert.severity,
      confidence:  alert.confidence,
      timestamp:   alert.timestamp,
      model_name:  alert.model_name,
      model_version: alert.model_version,
      all_probabilities: alert.all_probabilities,
      is_resolved: false,
      correlated:  alert.correlated,
      original_severity: alert.original_severity,
    })
    closeToast(alert.id)
  }

  const handleViewAll = () => {
    window.location.href = '/alerts'
  }

  if (toasts.length === 0 && !detailAlert) return null

  return (
    <>
      {/* Toast stack — góc phải trên */}
      <div className="fixed top-4 right-4 z-50 flex flex-col gap-3 pointer-events-none">
        {toasts.map((toast) => (
          <div key={toast.id} className="pointer-events-auto">
            {toast.isBatch ? (
              <BatchToast
                toast={toast}
                onClose={closeToast}
                onViewAll={handleViewAll}
              />
            ) : (
              <SingleToast
                toast={toast}
                onClose={closeToast}
                onViewDetail={handleViewDetail}
              />
            )}
          </div>
        ))}
      </div>

      {/* Detail modal */}
      {detailAlert && (
        <AlertDetailModal
          alert={detailAlert}
          onClose={() => setDetailAlert(null)}
        />
      )}
    </>
  )
}
