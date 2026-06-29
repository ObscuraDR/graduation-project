import { useState } from 'react'
import { X, Ban, Clock, FileText } from 'lucide-react'

const TIME_PRESETS = [
  { label: '7 tiếng', hours: 7 },
  { label: '24 tiếng', hours: 24 },
  { label: '3 ngày', hours: 72 },
  { label: 'Vĩnh viễn', hours: null },
]

export default function BlockIPModal({ isOpen, onClose, onBlock, initialIP = '' }) {
  const [ip, setIp] = useState(initialIP)
  const [reason, setReason] = useState('')
  const [selectedPreset, setSelectedPreset] = useState('24 tiếng')

  if (!isOpen) return null

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!ip.trim()) return
    const preset = TIME_PRESETS.find(p => p.label === selectedPreset)
    onBlock({
      ip_address: ip.trim(),
      reason: reason.trim() || undefined,
      expires_hours: preset?.hours || undefined,
    })
    // Reset form
    setIp('')
    setReason('')
    setSelectedPreset('24 tiếng')
  }

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl max-w-md w-full"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-50 text-red-600 rounded-lg">
              <Ban className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-gray-900">Block IP Address</h2>
              <p className="text-xs text-gray-500">Add IP to blacklist</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg">
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* IP Address */}
          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-1.5">
              <Ban className="w-4 h-4 text-red-600" />
              IP Address *
            </label>
            <input
              type="text"
              value={ip}
              onChange={(e) => setIp(e.target.value)}
              placeholder="e.g., 192.168.1.100"
              required
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-red-500"
            />
          </div>

          {/* Reason */}
          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-1.5">
              <FileText className="w-4 h-4 text-gray-600" />
              Reason (optional)
            </label>
            <input
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g., Suspicious activity"
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-red-500"
            />
          </div>

          {/* Expiration */}
          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-1.5">
              <Clock className="w-4 h-4 text-gray-600" />
              Thời gian chặn
            </label>
            <select
              value={selectedPreset}
              onChange={(e) => setSelectedPreset(e.target.value)}
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-red-500"
            >
              {TIME_PRESETS.map((preset) => (
                <option key={preset.label} value={preset.label}>
                  {preset.label}
                </option>
              ))}
            </select>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2.5 border border-gray-200 rounded-lg text-sm text-gray-700 hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-2.5 bg-red-600 text-white rounded-lg text-sm hover:bg-red-500 transition-colors"
            >
              Block IP
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
