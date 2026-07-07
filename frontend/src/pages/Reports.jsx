import { useState, useEffect } from 'react'
import { FileText, Download, RefreshCw, Save, ChevronDown, Printer } from 'lucide-react'
import { fetchSecurityReport } from '../lib/api'
import SeverityBadge from '../components/SeverityBadge'
import { formatDatetime } from '../lib/datetime'

const SEVERITY_COLORS = {
  critical: 'bg-red-500', high: 'bg-orange-400', medium: 'bg-amber-400', low: 'bg-blue-400',
}

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

  useEffect(() => { loadReport(false) }, [hours])

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

  const exportPDF = () => {
    if (!report) return
    // Tạo HTML cho PDF rồi in qua window.print()
    const html = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="UTF-8">
        <title>Security Report — Z-Sentinel IDS</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 30px; color: #1e293b; font-size: 13px; }
          h1 { color: #1e40af; font-size: 22px; border-bottom: 2px solid #1e40af; padding-bottom: 8px; }
          h2 { color: #334155; font-size: 16px; margin-top: 24px; }
          .meta { color: #64748b; font-size: 12px; margin-bottom: 20px; }
          .kpi-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 16px 0; }
          .kpi-card { border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; text-align: center; }
          .kpi-value { font-size: 28px; font-weight: bold; margin: 4px 0; }
          .kpi-label { font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }
          .critical { color: #dc2626; } .high { color: #ea580c; } .medium { color: #d97706; } .low { color: #16a34a; }
          table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 12px; }
          th { background: #f1f5f9; padding: 8px 12px; text-align: left; font-weight: 600; border: 1px solid #e2e8f0; }
          td { padding: 7px 12px; border: 1px solid #e2e8f0; }
          tr:nth-child(even) td { background: #f8fafc; }
          .summary { background: #eff6ff; border-left: 4px solid #3b82f6; padding: 12px 16px; border-radius: 4px; margin: 16px 0; }
          .footer { margin-top: 40px; color: #94a3b8; font-size: 11px; text-align: center; border-top: 1px solid #e2e8f0; padding-top: 12px; }
          @media print { body { margin: 15px; } }
        </style>
      </head>
      <body>
        <h1>🛡️ Z-Sentinel IDS — Security Report</h1>
        <div class="meta">
          Kỳ báo cáo: ${report.period_start?.slice(0,10)} → ${report.period_end?.slice(0,10)} &nbsp;|&nbsp;
          Tạo lúc: ${new Date().toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' })}
        </div>

        <div class="summary">${report.summary || `Tổng cộng ${report.total_alerts} cảnh báo trong ${hours} giờ.`}</div>

        <h2>📊 Tổng quan</h2>
        <div class="kpi-grid">
          <div class="kpi-card"><div class="kpi-value">${report.total_alerts}</div><div class="kpi-label">Tổng cảnh báo</div></div>
          <div class="kpi-card"><div class="kpi-value critical">${report.critical_count}</div><div class="kpi-label">Critical</div></div>
          <div class="kpi-card"><div class="kpi-value high">${report.high_count}</div><div class="kpi-label">High</div></div>
          <div class="kpi-card"><div class="kpi-value medium">${report.medium_count}</div><div class="kpi-label">Medium</div></div>
          <div class="kpi-card"><div class="kpi-value low">${report.low_count}</div><div class="kpi-label">Low</div></div>
          <div class="kpi-card"><div class="kpi-value" style="color:#7c3aed">${report.auto_blocked_count}</div><div class="kpi-label">Auto-blocked</div></div>
        </div>

        ${report.top_attack_types?.length ? `
        <h2>⚔️ Loại tấn công</h2>
        <table>
          <tr><th>Loại tấn công</th><th>Số lần</th><th>Tỉ lệ</th></tr>
          ${report.top_attack_types.map(t => `
            <tr><td>${t.type}</td><td>${t.count}</td>
            <td>${report.total_alerts > 0 ? Math.round(t.count/report.total_alerts*100) : 0}%</td></tr>
          `).join('')}
        </table>` : ''}

        ${report.top_attackers?.length ? `
        <h2>🎯 IP tấn công nhiều nhất</h2>
        <table>
          <tr><th>#</th><th>IP Address</th><th>Số lần</th></tr>
          ${report.top_attackers.map((a, i) => `
            <tr><td>${i+1}</td><td style="font-family:monospace">${a.ip}</td><td>${a.count}</td></tr>
          `).join('')}
        </table>` : ''}

        <div class="footer">
          Z-Sentinel Intrusion Detection System &bull; Generated automatically &bull; ${new Date().getFullYear()}
        </div>
      </body>
      </html>
    `
    const win = window.open('', '_blank')
    win.document.write(html)
    win.document.close()
    setTimeout(() => { win.print(); }, 500)
  }

  const btnClass = "flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-sm rounded-lg transition-colors"
  const primaryBtnClass = "flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition-colors disabled:opacity-50 shadow-lg shadow-blue-500/20"

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Security Reports</h1>
          <p className="text-sm text-slate-500 mt-0.5">Tổng hợp an ninh mạng theo khoảng thời gian</p>
        </div>
        <div className="flex gap-2 items-center">
          <select value={hours} onChange={(e) => setHours(Number(e.target.value))}
            className="px-3 py-2 border border-slate-700 rounded-lg text-sm bg-slate-800 text-slate-300 focus:outline-none focus:border-blue-500 transition-colors">
            <option value={1}>Last 1 hour</option>
            <option value={6}>Last 6 hours</option>
            <option value={24}>Last 24 hours</option>
            <option value={168}>Last 7 days</option>
            <option value={720}>Last 30 days</option>
          </select>
          <button onClick={() => loadReport(false)} disabled={loading} className={primaryBtnClass}>
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          {report && (
            <>
              <button onClick={() => loadReport(true)} disabled={loading} className={primaryBtnClass}>
                <Save className="w-4 h-4" /> Save
              </button>
              <div className="relative export-dropdown">
                <button onClick={() => setShowExportDropdown(!showExportDropdown)} className={btnClass}>
                  <Download className="w-4 h-4" /> Export <ChevronDown className="w-4 h-4" />
                </button>
                {showExportDropdown && (
                  <div className="absolute right-0 mt-2 w-44 bg-slate-800 rounded-lg shadow-xl border border-slate-700 z-10">
                    <button onClick={() => { exportCSV(); setShowExportDropdown(false) }}
                      className="w-full text-left px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-700 flex items-center gap-2 rounded-t-lg transition-colors">
                      <Download className="w-4 h-4 text-emerald-400" /> CSV
                    </button>
                    <button onClick={() => { exportJSON(); setShowExportDropdown(false) }}
                      className="w-full text-left px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-700 flex items-center gap-2 transition-colors">
                      <Download className="w-4 h-4 text-violet-400" /> JSON
                    </button>
                    <button onClick={() => { exportPDF(); setShowExportDropdown(false) }}
                      className="w-full text-left px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-700 flex items-center gap-2 rounded-b-lg transition-colors">
                      <Printer className="w-4 h-4 text-blue-400" /> PDF (In)
                    </button>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {!report && !loading && (
        <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 p-16 text-center">
          <FileText className="w-12 h-12 mx-auto mb-3 text-slate-700" />
          <p className="text-slate-500">Chọn khoảng thời gian và nhấn Generate để tạo báo cáo</p>
        </div>
      )}

      {loading && (
        <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 p-16 text-center text-slate-500">
          <RefreshCw className="w-8 h-8 mx-auto mb-3 animate-spin opacity-50" />
          Đang tổng hợp dữ liệu...
        </div>
      )}

      {report && !loading && (
        <div className="space-y-6">
          {/* Period */}
          <div className="text-xs text-slate-500 bg-slate-900/40 border border-slate-800/40 rounded-lg px-4 py-2.5">
            Kỳ báo cáo:{' '}
            <span className="font-medium text-slate-400">{formatDatetime(report.period_start)}</span>
            {' → '}
            <span className="font-medium text-slate-400">{formatDatetime(report.period_end)}</span>
            {' · Generated: '}{formatDatetime(report.generated_at)}
          </div>

          {/* KPI Cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {[
              { label: 'Total Alerts', value: report.total_alerts, color: 'text-slate-200' },
              { label: 'Critical', value: report.critical_count, color: 'text-red-400' },
              { label: 'High', value: report.high_count, color: 'text-orange-400' },
              { label: 'Medium', value: report.medium_count, color: 'text-amber-400' },
              { label: 'Low', value: report.low_count, color: 'text-blue-400' },
              { label: 'Auto-Blocked', value: report.auto_blocked_count, color: 'text-violet-400' },
            ].map(({ label, value, color }) => (
              <div key={label} className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 p-4 text-center hover:border-slate-700/60 transition-all">
                <p className="text-xs text-slate-500 mb-1 uppercase tracking-wider">{label}</p>
                <p className={`text-3xl font-bold ${color}`}>{value}</p>
              </div>
            ))}
          </div>

          {/* Severity bar */}
          {report.total_alerts > 0 && (
            <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 p-5">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">Severity Distribution</h3>
              <div className="flex rounded-full overflow-hidden h-3">
                {['critical', 'high', 'medium', 'low'].map((sev) => {
                  const count = report[`${sev}_count`]
                  const pct = (count / report.total_alerts) * 100
                  return pct > 0 ? (
                    <div key={sev} title={`${sev}: ${count}`} style={{ width: `${pct}%` }}
                      className={`${SEVERITY_COLORS[sev]} transition-all`} />
                  ) : null
                })}
              </div>
              <div className="flex gap-4 mt-3">
                {['critical', 'high', 'medium', 'low'].map((sev) => (
                  <div key={sev} className="flex items-center gap-1.5">
                    <span className={`w-2.5 h-2.5 rounded-full ${SEVERITY_COLORS[sev]}`} />
                    <span className="text-xs text-slate-500 capitalize">{sev} ({report[`${sev}_count`]})</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Top tables */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Top Attack Types */}
            <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 p-5">
              <h3 className="text-sm font-semibold text-slate-300 mb-4">Top Attack Types</h3>
              {report.top_attack_types?.length > 0 ? (
                <table className="w-full text-sm">
                  <tbody className="divide-y divide-slate-800/60">
                    {report.top_attack_types.map((t, i) => (
                      <tr key={i}>
                        <td className="py-2.5 text-slate-300 font-medium">{t.type}</td>
                        <td className="py-2.5 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <div className="w-24 bg-slate-800 rounded-full h-1.5">
                              <div className="bg-blue-500 h-1.5 rounded-full"
                                style={{ width: `${(t.count / report.top_attack_types[0].count) * 100}%` }} />
                            </div>
                            <span className="text-slate-400 w-8 text-right">{t.count}</span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : <p className="text-sm text-slate-600">No attacks detected</p>}
            </div>

            {/* Top Attackers */}
            <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 p-5">
              <h3 className="text-sm font-semibold text-slate-300 mb-4">Top Attackers</h3>
              {report.top_attackers?.length > 0 ? (
                <table className="w-full text-sm">
                  <tbody className="divide-y divide-slate-800/60">
                    {report.top_attackers.map((a, i) => (
                      <tr key={i}>
                        <td className="py-2.5 font-mono text-xs text-blue-400">{a.ip}</td>
                        <td className="py-2.5 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <div className="w-24 bg-slate-800 rounded-full h-1.5">
                              <div className="bg-red-500 h-1.5 rounded-full"
                                style={{ width: `${(a.count / report.top_attackers[0].count) * 100}%` }} />
                            </div>
                            <span className="text-slate-400 w-8 text-right">{a.count}</span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : <p className="text-sm text-slate-600">No attackers recorded</p>}
            </div>
          </div>

          {/* Protection Summary */}
          <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 p-5">
            <h3 className="text-sm font-semibold text-slate-300 mb-3">Protection Summary</h3>
            <div className="flex gap-6 text-sm">
              <span className="text-slate-400">🚫 Auto-blocked IPs: <strong className="text-slate-200">{report.auto_blocked_count}</strong></span>
              <span className="text-slate-400">🌍 Geo-blocked countries: <strong className="text-slate-200">{report.geo_blocked_count}</strong></span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
