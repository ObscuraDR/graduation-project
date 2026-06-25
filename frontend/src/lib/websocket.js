/**
 * WebSocket hook cho real-time alerts.
 * Kết nối đến ws://localhost:8000/ws và nhận alerts dạng JSON.
 */

const WS_URL = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`

let socket = null;
let messageListeners = []; // Renamed from 'listeners' for clarity
let statusListeners = []; // New: for connection status changes
let reconnectTimer = null;
let shouldReconnect = true;
let reconnectAttempts = 0; // New: track reconnection attempts
const MAX_RECONNECT_DELAY = 30000; // New: Max delay 30 seconds
const BASE_RECONNECT_DELAY = 1000; // New: Base delay 1 second

function broadcastStatus(status) {
  statusListeners.forEach(fn => fn(status));
}

export function connectWebSocket() {
  // Prevent connecting if already open or connecting
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return;
  }

  shouldReconnect = true;
  broadcastStatus('connecting'); // Notify listeners about connection attempt

  socket = new WebSocket(WS_URL);

  socket.onopen = () => {
    console.log('[WS] Connected to', WS_URL);
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    reconnectAttempts = 0; // Reset attempts on successful connection
    broadcastStatus('connected'); // Notify listeners
  }

  socket.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data);
      messageListeners.forEach((fn) => fn(message));
    } catch (err) {
      console.warn('[WS] Failed to parse message:', event.data, err);
    }
  }

  socket.onclose = (event) => {
    console.log(`[WS] Disconnected (Code: ${event.code}, Reason: ${event.reason}).`);
    broadcastStatus('disconnected'); // Notify listeners

    if (!shouldReconnect) {
      console.log('[WS] Reconnection explicitly disabled.');
      return;
    }

    // Exponential backoff logic
    reconnectAttempts++;
    const delay = Math.min(BASE_RECONNECT_DELAY * (2 ** (reconnectAttempts - 1)), MAX_RECONNECT_DELAY);
    console.log(`[WS] Reconnecting in ${delay / 1000}s (attempt ${reconnectAttempts})...`);
    reconnectTimer = setTimeout(connectWebSocket, delay);
    broadcastStatus('reconnecting'); // Notify listeners
  }

  socket.onerror = (err) => {
    console.error('[WS] Error:', err);
    broadcastStatus('error'); // Notify listeners
    // onerror typically precedes onclose, so onclose will handle reconnection
    socket.close(); // This will trigger onclose, which handles the reconnection logic
  }
}

export function onWebSocketMessage(callback) {
  messageListeners.push(callback);
  return () => {
    messageListeners = messageListeners.filter((fn) => fn !== callback);
  }
}

// New function to subscribe to connection status changes
export function onWebSocketStatusChange(callback) {
  statusListeners.push(callback);
  return () => {
    statusListeners = statusListeners.filter((fn) => fn !== callback);
  };
}

export function disconnectWebSocket() {
  shouldReconnect = false;
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (socket) {
    socket.close(1000, "Client initiated disconnect"); // Use a standard close code
    socket = null;
  }
  messageListeners = [];
  statusListeners = []; // Clear status listeners too
  broadcastStatus('disconnected'); // Final status update
}

// New function to get current WebSocket status
export function getWebSocketStatus() {
  if (!socket) return 'disconnected';
  switch (socket.readyState) {
    case WebSocket.CONNECTING: return 'connecting';
    case WebSocket.OPEN: return 'connected';
    case WebSocket.CLOSING: return 'disconnecting';
    case WebSocket.CLOSED: return 'disconnected';
    default: return 'unknown';
  }
}

export function isConnected() {
  return socket && socket.readyState === WebSocket.OPEN;
}
