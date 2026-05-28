import clsx from 'clsx'

/**
 * Hiển thị confusion matrix dạng heatmap.
 * Props:
 *  - matrix: 2D array, rows = actual, cols = predicted
 *  - labels: array tên class
 */
export default function ConfusionMatrix({ matrix, labels }) {
  if (!matrix || !labels) return null

  // Tính max để normalize màu sắc
  const flat = matrix.flat()
  const maxVal = Math.max(...flat)

  const cellColor = (value, isDiagonal) => {
    if (maxVal === 0) return 'bg-gray-50'
    const intensity = value / maxVal
    if (isDiagonal) {
      // Đường chéo (correct predictions) — màu xanh
      if (intensity > 0.7) return 'bg-green-600 text-white'
      if (intensity > 0.4) return 'bg-green-400 text-white'
      if (intensity > 0.1) return 'bg-green-200 text-gray-900'
      if (intensity > 0)   return 'bg-green-50 text-gray-700'
      return 'bg-gray-50 text-gray-400'
    } else {
      // Off-diagonal (errors) — màu đỏ
      if (intensity > 0.5) return 'bg-red-500 text-white'
      if (intensity > 0.2) return 'bg-red-300 text-gray-900'
      if (intensity > 0)   return 'bg-red-100 text-gray-800'
      return 'bg-gray-50 text-gray-400'
    }
  }

  return (
    <div className="overflow-x-auto">
      <table className="border-collapse">
        <thead>
          <tr>
            <th className="p-2 text-xs font-medium text-gray-500"></th>
            <th
              colSpan={labels.length}
              className="p-2 text-xs font-semibold text-gray-600 text-center"
            >
              Predicted →
            </th>
          </tr>
          <tr>
            <th className="p-2 text-xs font-medium text-gray-500 text-right">Actual ↓</th>
            {labels.map((label) => (
              <th
                key={label}
                className="p-2 text-xs font-semibold text-gray-700 border border-gray-200 bg-gray-50"
              >
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={i}>
              <th className="p-2 text-xs font-semibold text-gray-700 border border-gray-200 bg-gray-50 text-right">
                {labels[i]}
              </th>
              {row.map((value, j) => (
                <td
                  key={j}
                  className={clsx(
                    'p-3 text-center border border-gray-200 font-mono text-sm font-medium min-w-[60px]',
                    cellColor(value, i === j)
                  )}
                >
                  {value}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 bg-green-500 rounded inline-block" /> Correct predictions
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 bg-red-400 rounded inline-block" /> Misclassifications
        </span>
      </div>
    </div>
  )
}
