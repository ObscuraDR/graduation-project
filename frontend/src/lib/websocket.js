/**
 * WebSocket hook cho real-time alerts.
 * Kết nối đến ws://localhost:8000/ws và nhận alerts dạng JSON.
 */

const WS_URL = `ws://${window.location.hostname}:8000/ws`

let socket = null
let listeners = []
let reconnectTimer = null

export function connectWebSocket() {
  if (socket && socket.readyState === WebSocket.OPEN) return

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
  if (socket) {
    socket.close()
    socket = null
  }
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  listeners = []
}

export function isConnected() {
  return socket && socket.readyState === WebSocket.OPEN
}
