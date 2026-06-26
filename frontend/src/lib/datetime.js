/**
 * Datetime helpers — hiển thị thời gian đúng múi giờ Việt Nam (UTC+7)
 *
 * Backend lưu tất cả timestamps theo UTC (ISO 8601).
 * Các hàm này convert sang giờ Việt Nam khi hiển thị.
 */

const VN_LOCALE = 'vi-VN'
const VN_TZ = 'Asia/Ho_Chi_Minh'

/**
 * Format datetime đầy đủ: "26/06/2026, 10:30:45"
 */
export function formatDatetime(isoString) {
  if (!isoString) return '—'
  try {
    return new Date(isoString).toLocaleString(VN_LOCALE, { timeZone: VN_TZ })
  } catch {
    return isoString
  }
}

/**
 * Format chỉ giờ phút giây: "10:30:45"
 */
export function formatTime(isoString) {
  if (!isoString) return '—'
  try {
    return new Date(isoString).toLocaleTimeString(VN_LOCALE, { timeZone: VN_TZ })
  } catch {
    return isoString
  }
}

/**
 * Format chỉ ngày: "26/06/2026"
 */
export function formatDate(isoString) {
  if (!isoString) return '—'
  try {
    return new Date(isoString).toLocaleDateString(VN_LOCALE, { timeZone: VN_TZ })
  } catch {
    return isoString
  }
}

/**
 * Format giờ phút giây cho biểu đồ XAxis: "10:30:45"
 */
export function formatChartTime(isoString) {
  if (!isoString) return ''
  try {
    return new Date(isoString).toLocaleTimeString(VN_LOCALE, {
      timeZone: VN_TZ,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
  } catch {
    return isoString
  }
}

/**
 * Format giờ phút cho biểu đồ trend (attack trend chart): "10:30"
 */
export function formatChartHour(isoString) {
  if (!isoString) return ''
  try {
    return new Date(isoString).toLocaleTimeString(VN_LOCALE, {
      timeZone: VN_TZ,
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })
  } catch {
    return isoString?.slice(11, 16) || ''
  }
}

/**
 * Lấy giờ hiện tại theo giờ VN cho live chart
 */
export function nowTimeVN() {
  return new Date().toLocaleTimeString(VN_LOCALE, { timeZone: VN_TZ })
}
