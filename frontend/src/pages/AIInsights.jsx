import { useEffect, useState } from 'react'
import { Brain, BarChart3, Target, TrendingUp, Activity, Zap } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, PieChart, Pie, Legend } from 'recharts'
import StatCard from '../components/StatCard'
import ConfusionMatrix from '../components/ConfusionMatrix'
import { fetchAlertEngineStats, fetchTrainingReport, explainPrediction } from '../lib/api'
import { formatDatetime } from '../lib/datetime'

// Module-level cache — training report không thay đổi thường xuyên
let _trainingReportCache = null
let _engineStatsCache = null

// Per-class Precision / Recall / F1 calculated from confusion matrix
const ATTACK_COLORS = {
  DDoS: '#ef4444',
  PortScan: '#f59e0b',
  BruteForce: '#3b82f6',
  Botnet: '#8b5cf6',
  Abnormal: '#ec4899',
  Normal: '#22c55e',
  default: '#94a3b8',
}

const SEVERITY_COLORS = {
  critical: '#ef4444',
  high: '#f59e0b',
  medium: '#3b82f6',
  low: '#22c55e',
}

// Per-class Precision / Recall / F1 calculated from confusion matrix
function PerClassMetrics({ matrix, labels }) {
  if (!matrix || !labels) return null

  const metrics = labels.map((label, i) => {
    const tp = matrix[i][i]
    const fp = matrix.reduce((s, row, r) => r !== i ? s + row[i] : s, 0)
    const fn = matrix[i].reduce((s, v, c) => c !== i ? s + v : s, 0)
    const precision = tp + fp > 0 ? tp / (tp + fp) : 0
    const recall = tp + fn > 0 ? tp / (tp + fn) : 0
    const f1 = precision + recall > 0 ? 2 * precision * recall / (precision + recall) : 0
    return { label, precision, recall, f1, tp, fp, fn }
  })

  const pct = (v) => `${(v * 100).toFixed(1)}%`
  const color = (v) => v >= 0.95 ? 'text-green-600' : v >= 0.80 ? 'text-yellow-600' : 'text-red-500'

  return (
    <div className="flex-1 min-w-[260px]">
      <h4 className="text-sm font-semibold text-gray-700 mb-3">Per-class Metrics</h4>
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-gray-50">
            <th className="text-left p-2 text-xs font-semibold text-gray-600 border border-gray-200">Class</th>
            <th className="text-center p-2 text-xs font-semibold text-gray-600 border border-gray-200">Precision</th>
            <th className="text-center p-2 text-xs font-semibold text-gray-600 border border-gray-200">Recall</th>
            <th className="text-center p-2 text-xs font-semibold text-gray-600 border border-gray-200">F1</th>
          </tr>
        </thead>
        <tbody>
          {metrics.map(({ label, precision, recall, f1 }) => (
            <tr key={label} className="hover:bg-gray-50">
              <td className="p-2 border border-gray-200 font-medium text-gray-800">{label}</td>
              <td className={`p-2 border border-gray-200 text-center font-mono font-medium ${color(precision)}`}>{pct(precision)}</td>
              <td className={`p-2 border border-gray-200 text-center font-mono font-medium ${color(recall)}`}>{pct(recall)}</td>
              <td className={`p-2 border border-gray-200 text-center font-mono font-medium ${color(f1)}`}>{pct(f1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex gap-4 mt-3 text-xs text-gray-500">
        <span className="flex items-center gap-1"><span className="w-2 h-2 bg-green-500 rounded-full" />≥ 95%</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 bg-yellow-400 rounded-full" />≥ 80%</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 bg-red-400 rounded-full" />&lt; 80%</span>
      </div>
    </div>
  )
}

// Sample features for XAI demo
const SAMPLE_ATTACK_FEATURES = {
  flow_duration: 1.5, total_fwd_packets: 500, total_bwd_packets: 10,
  total_fwd_bytes: 50000, total_bwd_bytes: 1000, avg_packet_size: 100.0,
  packet_rate: 1200.0, byte_rate: 98000.0, syn_count: 450, fin_count: 2,
  rst_count: 5, psh_count: 10, ack_count: 50, unique_dst_ports: 1,
  inter_arrival_time_mean: 0.001, fwd_packet_rate: 1100.0,
  bwd_packet_rate: 100.0, fwd_byte_rate: 90000.0,
  bwd_byte_rate: 8000.0, packet_length_mean: 100.0,
}

export default function AIInsights() {
  const [engineStats, setEngineStats] = useState(_engineStatsCache)
  const [trainingReport, setTrainingReport] = useState(_trainingReportCache)
  const [reportError, setReportError] = useState(null)
  const [xaiResult, setXaiResult] = useState(null)
  const [xaiLoading, setXaiLoading] = useState(false)
  const [xaiError, setXaiError] = useState(null)

  useEffect(() => {
    // Fetch song song cả 2
    Promise.allSettled([
      fetchAlertEngineStats(),
      _trainingReportCache ? Promise.resolve(_trainingReportCache) : fetchTrainingReport(),
    ]).then(([statsRes, reportRes]) => {
      if (statsRes.status === 'fulfilled') {
        setEngineStats(statsRes.value)
        _engineStatsCache = statsRes.value
      }
      if (reportRes.status === 'fulfilled') {
        setTrainingReport(reportRes.value)
        _trainingReportCache = reportRes.value
      } else {
        setReportError(reportRes.reason?.response?.data?.detail || 'Training report not available')
      }
    })
  }, [])

  const runExplanation = async () => {
    setXaiLoading(true)
    setXaiError(null)
    try {
      const result = await explainPrediction(SAMPLE_ATTACK_FEATURES)
      setXaiResult(result.data)
    } catch (err) {
      setXaiError(err.response?.data?.detail?.message || err.message)
    }
    setXaiLoading(false)
  }

  const topFeaturesData = xaiResult?.top_features?.map((f) => ({
    name: f.feature.replace(/_/g, ' '),
    value: Math.abs(f.shap_value),
    shap: f.shap_value,
    raw: f.value,
  })) || []

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">AI Insights</h1>
        <p className="text-sm text-gray-500">Model performance metrics and explainability (SHAP)</p>
      </div>

      {/* Training Metrics */}
      {trainingReport ? (
        <>
          <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide">
            Model Training Performance
          </h2>
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">Model Performance Metrics</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[
                { title: 'Accuracy', value: trainingReport.metrics.accuracy, icon: Target, higherBetter: true },
                { title: 'Precision (macro)', value: trainingReport.metrics.precision_macro, icon: TrendingUp, higherBetter: true },
                { title: 'Recall (macro)', value: trainingReport.metrics.recall_macro, icon: Activity, higherBetter: true },
                { title: 'F1 Score', value: trainingReport.metrics.f1_macro, icon: Zap, higherBetter: true },
                { title: 'False Positive Rate', value: trainingReport.metrics.false_positive_rate, icon: Target, higherBetter: false },
                { title: 'Test Samples', value: null, icon: BarChart3, isCount: true,
                  count: trainingReport.test_samples, subtitle: `Train: ${trainingReport.train_samples?.toLocaleString()}` },
              ].map(({ title, value, icon: Icon, higherBetter, isCount, count, subtitle }) => {
                const good = higherBetter ? value >= 0.95 : value <= 0.03
                const warn = higherBetter ? value >= 0.80 : value <= 0.10
                const borderColor = isCount ? 'border-blue-200' : good ? 'border-green-200' : warn ? 'border-yellow-200' : 'border-red-200'
                const badgeColor = isCount ? 'bg-blue-50 text-blue-600' : good ? 'bg-green-50 text-green-600' : warn ? 'bg-yellow-50 text-yellow-600' : 'bg-red-50 text-red-600'
                const barColor = isCount ? 'bg-blue-400' : good ? 'bg-green-500' : warn ? 'bg-yellow-400' : 'bg-red-400'
                const barWidth = isCount ? 100 : higherBetter ? value * 100 : Math.max(0, (1 - value) * 100)
                const label = isCount ? count?.toLocaleString() : `${(value * 100).toFixed(value < 0.01 ? 3 : 2)}%`
                return (
                  <div key={title} className={`rounded-xl border-2 ${borderColor} p-4 flex flex-col gap-2`}>
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{title}</span>
                      <span className={`p-1.5 rounded-lg ${badgeColor}`}><Icon className="w-4 h-4" /></span>
                    </div>
                    <p className="text-2xl font-bold text-gray-900">{label}</p>
                    {subtitle && <p className="text-xs text-gray-400">{subtitle}</p>}
                    {!isCount && (
                      <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-700 ${barColor}`}
                          style={{ width: `${barWidth}%` }}
                        />
                      </div>
                    )}
                    {!isCount && (
                      <p className="text-xs font-medium" style={{ color: good ? '#16a34a' : warn ? '#ca8a04' : '#dc2626' }}>
                        {good ? '✓ Excellent' : warn ? '~ Good' : '✗ Needs improvement'}
                      </p>
                    )}
                  </div>
                )
              })}
            </div>
          </div>

          {/* Confusion Matrix + Per-class Metrics */}
          {trainingReport.metrics.confusion_matrix && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h3 className="text-sm font-semibold text-gray-700 mb-4">Confusion Matrix</h3>
              <div className="flex flex-col lg:flex-row gap-8">
                <ConfusionMatrix
                  matrix={trainingReport.metrics.confusion_matrix}
                  labels={trainingReport.metrics.class_names || trainingReport.class_names}
                />
                <PerClassMetrics
                  matrix={trainingReport.metrics.confusion_matrix}
                  labels={trainingReport.metrics.class_names || trainingReport.class_names}
                />
              </div>
            </div>
          )}

          {/* Model Info */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">Model Information</h3>

            {/* Badges */}
            <div className="flex flex-wrap gap-2 mb-5">
              <span className="flex items-center gap-1.5 px-3 py-1 bg-blue-100 text-blue-800 text-xs font-semibold rounded-full">
                🤖 {(trainingReport.model_params?.algorithm || trainingReport.model_type || 'RF').toUpperCase()}
              </span>
              <span className="flex items-center gap-1.5 px-3 py-1 bg-green-100 text-green-800 text-xs font-semibold rounded-full">
                ✅ Model Loaded
              </span>
              <span className="flex items-center gap-1.5 px-3 py-1 bg-purple-100 text-purple-800 text-xs font-semibold rounded-full">
                🎯 {trainingReport.n_features} Features
              </span>
              <span className="flex items-center gap-1.5 px-3 py-1 bg-yellow-100 text-yellow-800 text-xs font-semibold rounded-full">
                📦 {trainingReport.n_classes} Classes
              </span>
              <span className="flex items-center gap-1.5 px-3 py-1 bg-gray-100 text-gray-700 text-xs font-semibold rounded-full">
                🔢 v1.0
              </span>
            </div>

            {/* Timeline */}
            <div className="relative border-l-2 border-gray-200 ml-2 space-y-5">
              {/* Training Date */}
              <div className="relative pl-6">
                <span className="absolute -left-[9px] top-1 w-4 h-4 bg-blue-500 rounded-full border-2 border-white" />
                <p className="text-xs font-semibold text-blue-600 uppercase tracking-wide">Trained On</p>
                <p className="text-sm font-medium text-gray-900 mt-0.5">
                  {formatDatetime(trainingReport.training_date)}
                </p>
              </div>

              {/* Dataset */}
              <div className="relative pl-6">
                <span className="absolute -left-[9px] top-1 w-4 h-4 bg-purple-500 rounded-full border-2 border-white" />
                <p className="text-xs font-semibold text-purple-600 uppercase tracking-wide">Dataset</p>
                <p className="text-sm font-medium text-gray-900 mt-0.5">
                  {trainingReport.dataset_path?.split(/[\/\\]/).pop() || 'N/A'}
                </p>
                <p className="text-xs text-gray-500 mt-0.5">
                  {trainingReport.train_samples?.toLocaleString()} train / {trainingReport.test_samples?.toLocaleString()} test samples
                  {trainingReport.test_size ? ` (${(trainingReport.test_size * 100).toFixed(0)}% split)` : ''}
                </p>
              </div>

              {/* Model Config */}
              <div className="relative pl-6">
                <span className="absolute -left-[9px] top-1 w-4 h-4 bg-yellow-500 rounded-full border-2 border-white" />
                <p className="text-xs font-semibold text-yellow-600 uppercase tracking-wide">Hyperparameters</p>
                <div className="flex flex-wrap gap-2 mt-1.5">
                  {[
                    ['n_estimators', trainingReport.model_params?.n_estimators],
                    ['max_depth', trainingReport.model_params?.max_depth],
                    ['criterion', trainingReport.model_params?.criterion],
                    ['max_features', trainingReport.model_params?.max_features],
                    ['class_weight', trainingReport.model_params?.class_weight],
                    ['random_state', trainingReport.model_params?.random_state],
                  ].filter(([, v]) => v != null).map(([k, v]) => (
                    <span key={k} className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded font-mono">
                      {k}: <span className="text-gray-900 font-semibold">{String(v)}</span>
                    </span>
                  ))}
                </div>
              </div>

              {/* Classes */}
              <div className="relative pl-6">
                <span className="absolute -left-[9px] top-1 w-4 h-4 bg-red-400 rounded-full border-2 border-white" />
                <p className="text-xs font-semibold text-red-500 uppercase tracking-wide">Attack Classes</p>
                <div className="flex flex-wrap gap-2 mt-1.5">
                  {(trainingReport.class_names || trainingReport.metrics?.class_names || []).map((cls) => (
                    <span
                      key={cls}
                      className="px-2 py-0.5 text-xs font-semibold rounded-full"
                      style={{ backgroundColor: (ATTACK_COLORS[cls] || ATTACK_COLORS.default) + '22', color: ATTACK_COLORS[cls] || ATTACK_COLORS.default }}
                    >
                      {cls}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </>
      ) : reportError ? (
        <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-800">
          ⚠️ {reportError}. Run <code className="bg-yellow-100 px-1 rounded">python backend/scripts/generate_and_train.py</code> to generate.
        </div>
      ) : null}

      {/* Alert Engine Runtime Stats */}
      {engineStats && (
        <>
          <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide pt-4">
            Runtime Alert Statistics
          </h2>
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 divide-y md:divide-y-0 md:divide-x md:flex">
            {[
              {
                title: 'Total Alerts',
                value: engineStats.total_alerts,
                subtitle: 'All time',
                icon: Brain,
                color: engineStats.total_alerts > 100 ? '#ef4444' : engineStats.total_alerts > 50 ? '#f59e0b' : '#8b5cf6',
                bg: engineStats.total_alerts > 100 ? 'bg-red-50' : engineStats.total_alerts > 50 ? 'bg-yellow-50' : 'bg-purple-50',
              },
              {
                title: 'Active Attackers',
                value: engineStats.active_attackers,
                subtitle: engineStats.active_attackers > 0 ? '⚠ IPs being tracked' : '✓ No active threats',
                icon: BarChart3,
                color: engineStats.active_attackers > 0 ? '#ef4444' : '#22c55e',
                bg: engineStats.active_attackers > 0 ? 'bg-red-50' : 'bg-green-50',
              },
              {
                title: 'Confidence Threshold',
                value: `${(engineStats.confidence_threshold * 100).toFixed(0)}%`,
                subtitle: 'Min score to alert',
                icon: Target,
                color: '#3b82f6',
                bg: 'bg-blue-50',
              },
              {
                title: 'Alert Cooldown',
                value: `${engineStats.alert_cooldown}s`,
                subtitle: 'Per attacker IP',
                icon: Activity,
                color: '#f59e0b',
                bg: 'bg-yellow-50',
              },
            ].map(({ title, value, subtitle, icon: Icon, color, bg }) => (
              <div key={title} className="flex-1 flex items-center gap-4 px-6 py-5">
                <div className={`p-3 rounded-xl ${bg} shrink-0`}>
                  <Icon className="w-5 h-5" style={{ color }} />
                </div>
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{title}</p>
                  <p className="text-2xl font-bold text-gray-900 leading-tight" style={{ color }}>{value}</p>
                  <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>
                </div>
              </div>
            ))}
          </div>

          {engineStats.alerts_by_type && Object.keys(engineStats.alerts_by_type).length > 0 && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Alerts by Attack Type */}
              <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
                <h3 className="text-sm font-semibold text-gray-700 mb-4">Alerts by Attack Type</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={Object.entries(engineStats.alerts_by_type).map(([name, value]) => ({ name, value }))} margin={{ top: 16 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(v) => [v, 'Alerts']} />
                    <Bar dataKey="value" radius={[4, 4, 0, 0]} label={{ position: 'top', fontSize: 11, fill: '#6b7280' }}>
                      {Object.keys(engineStats.alerts_by_type).map((key, i) => (
                        <Cell key={key} fill={ATTACK_COLORS[key] || ATTACK_COLORS.default} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Alerts by Severity */}
              {engineStats.alerts_by_severity && Object.keys(engineStats.alerts_by_severity).length > 0 && (
                <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
                  <h3 className="text-sm font-semibold text-gray-700 mb-4">Alerts by Severity</h3>
                  <ResponsiveContainer width="100%" height={250}>
                    <PieChart>
                      <Pie
                        data={Object.entries(engineStats.alerts_by_severity).map(([name, value]) => ({ name, value }))}
                        dataKey="value"
                        nameKey="name"
                        cx="50%" cy="50%"
                        outerRadius={90}
                        label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                        labelLine={false}
                      >
                        {Object.keys(engineStats.alerts_by_severity).map((key) => (
                          <Cell key={key} fill={SEVERITY_COLORS[key] || '#94a3b8'} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(v) => [v, 'Alerts']} />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* XAI Section */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-gray-700">SHAP Explanation</h3>
            <p className="text-xs text-gray-400">Explain why the model made a specific prediction</p>
          </div>
          <button
            onClick={runExplanation}
            disabled={xaiLoading}
            className="px-4 py-2 bg-purple-600 text-white text-sm rounded-lg hover:bg-purple-700 disabled:opacity-50"
          >
            {xaiLoading ? 'Analyzing...' : 'Run Explanation'}
          </button>
        </div>

        {xaiError && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 mb-4">
            {xaiError}
          </div>
        )}

        {xaiResult && (
          <div className="space-y-4">
            <div className="flex gap-4 text-sm flex-wrap">
              <span className="px-3 py-1 bg-purple-100 text-purple-800 rounded-full font-medium">
                Predicted: {xaiResult.predicted_label}
              </span>
              <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full font-medium">
                Confidence: {(xaiResult.confidence * 100).toFixed(1)}%
              </span>
            </div>

            <h4 className="text-sm font-medium text-gray-600">Top Contributing Features (SHAP values)</h4>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={topFeaturesData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={140} />
                <Tooltip formatter={(v) => v.toFixed(4)} />
                <Bar dataKey="value" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {!xaiResult && !xaiError && (
          <p className="text-sm text-gray-400 text-center py-8">
            Click "Run Explanation" to analyze a sample attack prediction with SHAP
          </p>
        )}
      </div>
    </div>
  )
}
