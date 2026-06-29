import { useState, useEffect } from 'react'
import { FileText, Download, RefreshCw, Save, ChevronDown } from 'lucide-react'
import { fetchSecurityReport } from '../lib/api'
import SeverityBadge from '../components/SeverityBadge'
import { formatDatetime } from '../lib/datetime'

export default function Reports() {
  const [hours, setHours] = useState(24)
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [showExportDropdown, setShowExportDropdown] = useState(false)

  const loadReport = async (save = false) => {
    setLoading(true)
    try {
      const data = await fetchSecurityReport(hours, save)
      setReport(data)
    } catch (err) {
      console.error('Failed to load report:', err)
    }
    setLoading(false)
  }

  // Auto-generate when hours changes
  useEffect(() => {
    loadReport(false)
  }, [hours])

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (showExportDropdown && !event.target.closest('.export-dropdown')) {
        setShowExportDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [showExportDropdown])

  const exportJSON = () => {
    if (!report) return
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `security-report-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const exportCSV = () => {
    if (!report) return
    const lines = [
      `Security Report — ${report.period_start} to ${report.period_end}`,
      '',
      'Metric,Value',
      `Total Alerts,${report.total_alerts}`,
      `Critical,${report.critical_count}`,
      `High,${report.high_count}`,
      `Medium,${report.medium_count}`,
      `Low,${report.low_count}`,
      `Auto-blocked IPs,${report.auto_blocked_count}`,
      `Geo-blocked Countries,${report.geo_blocked_count}`,
      '',
      'Top Attack Types',
      'Type,Count',
      ...(report.top_attack_types || []).map((t) => `${t.type},${t.count}`),
      '',
      'Top Attackers',
      'IP,Count',
      ...(report.top_attackers || []).map((a) => `${a.ip},${a.count}`),
    ]
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `security-report-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const SEVERITY_COLORS = {
    critical: 'bg-red-500', high: 'bg-orange-400', medium: 'bg-yellow-400', low: 'bg-blue-400',
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Security Reports</h1>
          <p className="text-sm text-gray-500">Tổng hợp an ninh mạng theo khoảng thời gian</p>
        </div>
        <div className="flex gap-2">
          <select value={hours} onChange={(e) => setHours(Number(e.target.value))}
            className="px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white text-gray-700">
            <option value={1}>Last 1 hour</option>
            <option value={6}>Last 6 hours</option>
            <option value={24}>Last 24 hours</option>
            <option value={168}>Last 7 days</option>
            <option value={720}>Last 30 days</option>
          </select>
          <button onClick={() => loadReport(false)} disabled={loading}
            className="flex items-center justify-center gap-2 px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-500 disabled:opacity-50 transition-colors"
            title="Refresh report">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          {report && (
            <>
              <button onClick={() => loadReport(true)} disabled={loading}
                className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-500 disabled:opacity-50 transition-colors">
                <Save className="w-4 h-4" /> Save
              </button>
              <div className="relative export-dropdown">
                <button
                  onClick={() => setShowExportDropdown(!showExportDropdown)}
                  className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-500 disabled:opacity-50 transition-colors"
                >
                  <Download className="w-4 h-4" /> Export <ChevronDown className="w-4 h-4" />
                </button>
                {showExportDropdown && (
                  <div className="absolute right-0 mt-2 w-40 bg-white rounded-lg shadow-lg border border-gray-200 z-10">
                    <button
                      onClick={() => {
                        exportCSV()
                        setShowExportDropdown(false)
                      }}
                      className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2"
                    >
                      <Download className="w-4 h-4 text-green-600" /> CSV
                    </button>
                    <button
                      onClick={() => {
                        exportJSON()
                        setShowExportDropdown(false)
                      }}
                      className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2"
                    >
                      <Download className="w-4 h-4 text-purple-600" /> JSON
                    </button>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {!report && !loading && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-16 text-center">
          <FileText className="w-12 h-12 mx-auto mb-3 text-gray-300" />
          <p className="text-gray-400">Chọn khoảng thời gian và nhấn Generate để tạo báo cáo</p>
        </div>
      )}

      {loading && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-16 text-center text-gray-400">
          Đang tổng hợp dữ liệu...
        </div>
      )}

      {report && !loading && (
        <div className="space-y-6">
          {/* Period */}
          <div className="text-xs text-gray-500">
            Kỳ báo cáo: <span className="font-medium">{formatDatetime(report.period_start)}</span>
            {' → '}
            <span className="font-medium">{formatDatetime(report.period_end)}</span>
            {' | Generated: '}{formatDatetime(report.generated_at)}
          </div>

          {/* KPI Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {[
              { label: 'Total Alerts', value: report.total_alerts, color: 'text-gray-800' },
              { label: 'Critical', value: report.critical_count, color: 'text-red-600' },
              { label: 'High', value: report.high_count, color: 'text-orange-500' },
              { label: 'Medium', value: report.medium_count, color: 'text-yellow-600' },
              { label: 'Low', value: report.low_count, color: 'text-blue-500' },
              { label: 'Auto-Blocked', value: report.auto_blocked_count, color: 'text-purple-600' },
            ].map(({ label, value, color }) => (
              <div key={label} className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 text-center">
                <p className="text-xs text-gray-500 mb-1">{label}</p>
                <p className={`text-3xl font-bold ${color}`}>{value}</p>
              </div>
            ))}
          </div>

          {/* Severity bar */}
          {report.total_alerts > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Severity Distribution</h3>
              <div className="flex rounded-full overflow-hidden h-4">
                {['critical', 'high', 'medium', 'low'].map((sev) => {
                  const count = report[`${sev}_count`]
                  const pct = (count / report.total_alerts) * 100
                  return pct > 0 ? (
                    <div key={sev} title={`${sev}: ${count}`} style={{ width: `${pct}%` }}
                      className={`${SEVERITY_COLORS[sev]} transition-all`} />
                  ) : null
                })}
              </div>
              <div className="flex gap-4 mt-2">
                {['critical', 'high', 'medium', 'low'].map((sev) => (
                  <div key={sev} className="flex items-center gap-1.5">
                    <span className={`w-2.5 h-2.5 rounded-full ${SEVERITY_COLORS[sev]}`} />
                    <span className="text-xs text-gray-600 capitalize">{sev} ({report[`${sev}_count`]})</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Top tables */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Top Attack Types */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Top Attack Types</h3>
              {report.top_attack_types?.length > 0 ? (
                <table className="w-full text-sm">
                  <tbody className="divide-y divide-gray-50">
                    {report.top_attack_types.map((t, i) => (
                      <tr key={i}>
                        <td className="py-2 text-gray-800 font-medium">{t.type}</td>
                        <td className="py-2 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <div className="w-24 bg-gray-100 rounded-full h-1.5">
                              <div className="bg-blue-500 h-1.5 rounded-full"
                                style={{ width: `${(t.count / report.top_attack_types[0].count) * 100}%` }} />
                            </div>
                            <span className="text-gray-600 w-8 text-right">{t.count}</span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : <p className="text-sm text-gray-400">No attacks detected</p>}
            </div>

            {/* Top Attackers */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Top Attackers</h3>
              {report.top_attackers?.length > 0 ? (
                <table className="w-full text-sm">
                  <tbody className="divide-y divide-gray-50">
                    {report.top_attackers.map((a, i) => (
                      <tr key={i}>
                        <td className="py-2 font-mono text-xs text-gray-800">{a.ip}</td>
                        <td className="py-2 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <div className="w-24 bg-gray-100 rounded-full h-1.5">
                              <div className="bg-red-500 h-1.5 rounded-full"
                                style={{ width: `${(a.count / report.top_attackers[0].count) * 100}%` }} />
                            </div>
                            <span className="text-gray-600 w-8 text-right">{a.count}</span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : <p className="text-sm text-gray-400">No attackers recorded</p>}
            </div>
          </div>

          {/* Geo & Auto-block summary */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Protection Summary</h3>
            <div className="flex gap-6 text-sm text-gray-600">
              <span>🚫 Auto-blocked IPs: <strong>{report.auto_blocked_count}</strong></span>
              <span>🌍 Geo-blocked countries: <strong>{report.geo_blocked_count}</strong></span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
