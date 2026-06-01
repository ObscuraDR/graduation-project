import { Component } from 'react'

/**
 * Error Boundary — bắt JavaScript errors trong component tree,
 * hiển thị fallback UI thay vì trang trắng.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo)
    this.setState({ errorInfo })
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-6">
          <div className="bg-red-50 border border-red-200 rounded-xl p-6">
            <h2 className="text-lg font-bold text-red-800 mb-2">
              ⚠️ Đã xảy ra lỗi khi render trang này
            </h2>
            <p className="text-sm text-red-700 mb-4">
              {this.state.error?.toString()}
            </p>
            {this.state.errorInfo && (
              <details className="text-xs text-red-600 bg-red-100 rounded p-3 overflow-auto max-h-64">
                <summary className="cursor-pointer font-medium mb-2">
                  Chi tiết stack trace
                </summary>
                <pre className="whitespace-pre-wrap">
                  {this.state.errorInfo.componentStack}
                </pre>
              </details>
            )}
            <button
              onClick={this.handleReset}
              className="mt-4 px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700"
            >
              Thử lại
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
