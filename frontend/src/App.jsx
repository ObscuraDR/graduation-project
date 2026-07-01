import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import RequireAuth from './components/RequireAuth';
import Sidebar from './components/Sidebar';
import ToastContainer from './components/ToastNotification';
import { connectWebSocket, onWebSocketMessage } from './lib/websocket';

import Login from './pages/Login';
import Overview from './pages/Overview';
import Alerts from './pages/Alerts';
import Firewall from './pages/Firewall';
import ServerManagement from './pages/ServerManagement';
import NotificationSettings from './pages/NotificationSettings';
import ProfileSettings from './pages/ProfileSettings';
import GeoBlocking from './pages/GeoBlocking';
import UserManagementAndAudit from './pages/UserManagementAndAudit';
import LogViewer from './pages/LogViewer';
import AIInsights from './pages/AIInsights';
import Network from './pages/Network';
import Reports from './pages/Reports';
import Register from './pages/Register';


export default function App() {
  const [liveAlerts, setLiveAlerts] = useState([])

  // Kết nối WebSocket ở App level — toàn cục, không phụ thuộc trang
  useEffect(() => {
    connectWebSocket()
    const unsub = onWebSocketMessage((msg) => {
      if (msg.type === 'alert') {
        setLiveAlerts((prev) => [msg.data, ...prev].slice(0, 50))
      }
    })
    return () => unsub()
  }, [])

  return (
    <BrowserRouter>
      {/* Toast notifications — hiển thị ở mọi trang */}
      <ToastContainer alerts={liveAlerts} />

      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        {/* Protected Routes */}
        <Route
          path="/*"
          element={
            <RequireAuth>
              <div className="flex min-h-screen bg-slate-950 text-slate-200">
                <Sidebar />
                <div className="flex-1 p-6">
                  <Routes>
                    <Route index element={<Overview />} />
                    <Route path="alerts" element={<Alerts />} />
                    <Route path="firewall" element={<Firewall />} />
                    <Route path="servers" element={<ServerManagement />} />
                    <Route path="settings/notifications" element={<NotificationSettings />} />
                    <Route path="settings/profile" element={<ProfileSettings />} />
                    <Route path="geo-blocking" element={<GeoBlocking />} />
                    <Route path="settings/users" element={<UserManagementAndAudit />} />
                    <Route path="ai-insights" element={<AIInsights />} />
                    <Route path="network" element={<Network />} />
                    <Route path="logs" element={<LogViewer />} />
                    <Route path="reports" element={<Reports />} />
                  </Routes>
                </div>
              </div>
            </RequireAuth>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}