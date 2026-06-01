/**
 * WebSocket hook cho real-time alerts.
 * Kết nối đến ws://localhost:8000/ws và nhận alerts dạng JSON.
 */

const WS_URL = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`

let socket = null
let listeners = []
let reconnectTimer = null
let shouldReconnect = true

export function connectWebSocket() {
  if (socket && socket.readyState === WebSocket.OPEN) return

  shouldReconnect = true
  socket = new WebSocket(WS_URL)

  socket.onopen = () => {
    console.log('[WS] Connected to', WS_URL)
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  socket.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data)
      listeners.forEach((fn) => fn(message))
    } catch (err) {
      console.warn('[WS] Failed to parse message:', event.data)
    }
  }

  socket.onclose = () => {
    if (!shouldReconnect) return
    console.log('[WS] Disconnected, reconnecting in 3s...')
    reconnectTimer = setTimeout(connectWebSocket, 3000)
  }

  socket.onerror = (err) => {
    console.error('[WS] Error:', err)
    socket.close()
  }
}

export function onWebSocketMessage(callback) {
  listeners.push(callback)
  return () => {
    listeners = listeners.filter((fn) => fn !== callback)
  }
}

export function disconnectWebSocket() {
  shouldReconnect = false
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  if (socket) {
    socket.close()
    socket = null
  }
  listeners = []
}

export function isConnected() {
  return socket && socket.readyState === WebSocket.OPEN
}
