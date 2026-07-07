import { X, Shield, AlertTriangle, Network, Clock, Brain } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import SeverityBadge from './SeverityBadge'
import { formatDatetime } from '../lib/datetime'

export default function AlertDetailModal({ alert, onClose }) {
  if (!alert) return null

  const probabilities = alert.all_probabilities
    ? Object.entries(alert.all_probabilities).map(([name, value]) => ({
        name,
        value: parseFloat((value * 100).toFixed(2)),
      }))
    : []

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-50 text-red-600 rounded-lg">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-gray-900">{alert.attack_type}</h2>
              <p className="text-xs text-gray-500 font-mono">{alert.alert_id}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg">
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Summary Row */}
          <div className="grid grid-cols-3 gap-4">
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-xs text-gray-500 mb-1">Severity</p>
              <SeverityBadge severity={alert.severity} />
              {alert.original_severity && alert.original_severity !== alert.severity && (
                <p className="text-xs text-gray-400 mt-1">
                  Escalated from <span className="font-medium">{alert.original_severity}</span>
                </p>
              )}
            </div>
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-xs text-gray-500 mb-1">Confidence</p>
              <p className="text-lg font-bold text-gray-900">
                {((alert.confidence ?? 0) * 100).toFixed(1)}%
              </p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-xs text-gray-500 mb-1">Status</p>
              <p className={`text-sm font-semibold ${alert.is_resolved ? 'text-green-600' : 'text-orange-600'}`}>
                {alert.is_resolved ? '✓ Resolved' : '● Active'}
              </p>
            </div>
          </div>

          {/* Network Info */}
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <Network className="w-4 h-4" /> Network Information
            </h3>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <InfoRow label="Source IP" value={`${alert.source_ip || alert.src_ip}:${alert.source_port || alert.src_port || '-'}`} mono />
              <InfoRow label="Destination IP" value={`${alert.dest_ip || alert.dst_ip}:${alert.dest_port || alert.dst_port || '-'}`} mono />
              <InfoRow label="Protocol" value={(alert.protocol || '-').toUpperCase()} />
              <InfoRow label="Flow Key" value={alert.flow_key || '-'} mono small />
            </div>
          </div>

          {/* Model Info */}
          {alert.model_name && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                <Brain className="w-4 h-4" /> Model Information
              </h3>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <InfoRow label="Model" value={alert.model_name} />
                <InfoRow label="Version" value={alert.model_version || '1.0'} />
              </div>
            </div>
          )}

          {/* Probability Distribution */}
          {probabilities.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Class Probabilities</h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={probabilities} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={100} />
                  <Tooltip formatter={(v) => `${v.toFixed(2)}%`} />
                  <Bar dataKey="value" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Timestamp */}
          <div className="flex items-center gap-2 text-sm text-gray-500 pt-3 border-t border-gray-100">
            <Clock className="w-4 h-4" />
            <span>Detected at: {formatDatetime(alert.timestamp)}</span>
          </div>

          {/* Threat Intelligence */}
          {alert.threat_intel && (
            <div className={`p-3 rounded-lg border ${
              alert.threat_intel.threat_level === 'critical' ? 'bg-red-50 border-red-200' :
              alert.threat_intel.threat_level === 'high' ? 'bg-orange-50 border-orange-200' :
              alert.threat_intel.threat_level === 'medium' ? 'bg-yellow-50 border-yellow-200' :
              'bg-gray-50 border-gray-200'
            }`}>
              <p className="text-xs font-semibold mb-1.5 flex items-center gap-1">
                🌐 Threat Intelligence
                <span className={`ml-auto px-1.5 py-0.5 rounded text-xs font-bold ${
                  alert.threat_intel.threat_level === 'critical' ? 'bg-red-100 text-red-700' :
                  alert.threat_intel.threat_level === 'high' ? 'bg-orange-100 text-orange-700' :
                  alert.threat_intel.threat_level === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                  'bg-gray-100 text-gray-600'
                }`}>
                  {alert.threat_intel.threat_level?.toUpperCase()}
                </span>
              </p>
              <div className="grid grid-cols-2 gap-1 text-xs text-gray-600">
                <span>Abuse Score: <b>{alert.threat_intel.abuse_score ?? 0}%</b></span>
                <span>ISP: {alert.threat_intel.isp || 'N/A'}</span>
                {alert.threat_intel.is_tor && <span className="text-red-600 font-medium">⚠ TOR Exit Node</span>}
                {alert.threat_intel.is_vpn && <span className="text-orange-600 font-medium">⚠ VPN/Proxy</span>}
              </div>
            </div>
          )}

          {/* Notes */}
          {alert.notes && (
            <div className="p-3 bg-blue-50 rounded-lg">
              <p className="text-xs text-blue-800 font-medium mb-1">Notes</p>
              <p className="text-sm text-blue-900">{alert.notes}</p>
            </div>
          )}

          {/* Correlation */}
          {alert.correlated && (
            <div className="p-3 bg-orange-50 rounded-lg flex items-start gap-2">
              <Shield className="w-4 h-4 text-orange-600 mt-0.5" />
              <div>
                <p className="text-xs text-orange-800 font-medium">Correlated Attack Pattern</p>
                <p className="text-sm text-orange-900">
                  Severity was escalated due to repeated attacks from this source.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function InfoRow({ label, value, mono = false, small = false }) {
  return (
    <div>
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`${small ? 'text-xs' : 'text-sm'} ${mono ? 'font-mono' : 'font-medium'} text-gray-900 mt-0.5`}>
        {value}
      </p>
    </div>
  )
}
