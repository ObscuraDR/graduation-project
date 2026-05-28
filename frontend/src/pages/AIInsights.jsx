import { useEffect, useState } from 'react'
import { Brain, BarChart3, Target, TrendingUp, Activity, Zap } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import StatCard from '../components/StatCard'
import ConfusionMatrix from '../components/ConfusionMatrix'
import { fetchAlertEngineStats, fetchTrainingReport, explainPrediction } from '../lib/api'

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
  const [engineStats, setEngineStats] = useState(null)
  const [trainingReport, setTrainingReport] = useState(null)
  const [reportError, setReportError] = useState(null)
  const [xaiResult, setXaiResult] = useState(null)
  const [xaiLoading, setXaiLoading] = useState(false)
  const [xaiError, setXaiError] = useState(null)

  useEffect(() => {
    fetchAlertEngineStats().then(setEngineStats).catch(console.error)
    fetchTrainingReport()
      .then(setTrainingReport)
      .catch((err) => setReportError(err.response?.data?.detail || 'Training report not available'))
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
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              title="Accuracy"
              value={`${(trainingReport.metrics.accuracy * 100).toFixed(2)}%`}
              icon={Target}
              color="green"
            />
            <StatCard
              title="Precision (macro)"
              value={`${(trainingReport.metrics.precision_macro * 100).toFixed(2)}%`}
              icon={TrendingUp}
              color="blue"
            />
            <StatCard
              title="Recall (macro)"
              value={`${(trainingReport.metrics.recall_macro * 100).toFixed(2)}%`}
              icon={Activity}
              color="purple"
            />
            <StatCard
              title="F1 Score"
              value={`${(trainingReport.metrics.f1_macro * 100).toFixed(2)}%`}
              icon={Zap}
              color="yellow"
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <StatCard
              title="False Positive Rate"
              value={`${(trainingReport.metrics.false_positive_rate * 100).toFixed(3)}%`}
              subtitle="Lower is better"
              icon={Target}
              color={trainingReport.metrics.false_positive_rate < 0.03 ? 'green' : 'yellow'}
            />
            <StatCard
              title="Test Samples"
              value={trainingReport.test_samples?.toLocaleString()}
              subtitle={`Training: ${trainingReport.train_samples?.toLocaleString()}`}
              icon={BarChart3}
              color="blue"
            />
          </div>

          {/* Confusion Matrix */}
          {trainingReport.metrics.confusion_matrix && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h3 className="text-sm font-semibold text-gray-700 mb-4">Confusion Matrix</h3>
              <ConfusionMatrix
                matrix={trainingReport.metrics.confusion_matrix}
                labels={trainingReport.metrics.class_names || trainingReport.class_names}
              />
            </div>
          )}

          {/* Model Info */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Model Information</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <p className="text-xs text-gray-500">Algorithm</p>
                <p className="font-medium text-gray-900">{trainingReport.model_params?.algorithm || trainingReport.model_type}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">N Estimators</p>
                <p className="font-medium text-gray-900">{trainingReport.model_params?.n_estimators || '-'}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Features</p>
                <p className="font-medium text-gray-900">{trainingReport.n_features}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Classes</p>
                <p className="font-medium text-gray-900">{trainingReport.n_classes}</p>
              </div>
              <div className="col-span-2 md:col-span-4">
                <p className="text-xs text-gray-500">Training Date</p>
                <p className="font-medium text-gray-900">{trainingReport.training_date?.slice(0, 19).replace('T', ' ')}</p>
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
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <StatCard title="Total Alerts" value={engineStats.total_alerts} icon={Brain} color="purple" />
            <StatCard title="Active Attackers" value={engineStats.active_attackers} icon={BarChart3} color="red" />
            <StatCard title="Confidence Threshold" value={`${(engineStats.confidence_threshold * 100).toFixed(0)}%`} color="blue" />
            <StatCard title="Cooldown" value={`${engineStats.alert_cooldown}s`} subtitle="Per-IP" color="yellow" />
          </div>

          {engineStats.alerts_by_type && Object.keys(engineStats.alerts_by_type).length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h3 className="text-sm font-semibold text-gray-700 mb-4">Alerts by Attack Type</h3>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={Object.entries(engineStats.alerts_by_type).map(([name, value]) => ({ name, value }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="value" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
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
