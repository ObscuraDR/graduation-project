import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import RequireAuth from './components/RequireAuth';
import Sidebar from './components/Sidebar';
import ToastContainer from './components/ToastNotification';
import { connectWebSocket, onWebSocketMessage } from './lib/websocket';

import Login from './pages/Login';
import Register from './pages/Register';
import Overview from './pages/Overview';
import Alerts from './pages/Alerts';
import Firewall from './pages/Firewall';
import ServerManagement from './pages/ServerManagement';
import NotificationSettings from './pages/NotificationSettings';
import ProfileSettings from './pages/ProfileSettings';
import UserManagement from './pages/UserManagement';
import AuditLogs from './pages/AuditLogs';
import LogViewer from './pages/LogViewer';
import AIInsights from './pages/AIInsights';
import Traffic from './pages/Traffic';
import Reports from './pages/Reports';
import Settings from './pages/Settings';

export default function App() {
  const [liveAlerts, setLiveAlerts] = useState([])

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
      <ToastContainer alerts={liveAlerts} />

      <Routes>
        <Route path="/login"    element={<Login />} />
        <Route path="/register" element={<Register />} />

        {/* Protected Routes */}
        <Route
          path="/*"
          element={
            <RequireAuth>
              <div className="flex min-h-screen bg-slate-950 text-slate-200">
                <Sidebar />
                <div className="flex-1 overflow-auto">
                  <Routes>
                    <Route index                      element={<Overview />} />
                    <Route path="alerts"              element={<Alerts />} />
                    <Route path="firewall"            element={<Firewall />} />
                    <Route path="servers"             element={<ServerManagement />} />
                    <Route path="traffic"             element={<Traffic />} />
                    {/* /network → redirect sang /traffic (Option B) */}
                    <Route path="network"             element={<Navigate to="/traffic" replace />} />
                    <Route path="logs"                element={<LogViewer />} />
                    <Route path="ai-insights"         element={<AIInsights />} />
                    <Route path="reports"             element={<Reports />} />
                    {/* Settings */}
                    <Route path="settings/profile"        element={<ProfileSettings />} />
                    <Route path="settings/notifications"  element={<NotificationSettings />} />
                    <Route path="settings/users"          element={<UserManagement />} />
                    <Route path="settings/pipeline"       element={<Settings />} />
                    <Route path="geo-blocking"            element={<Navigate to="/firewall" replace />} />
                    <Route path="audit"                   element={<AuditLogs />} />
                    {/* Fallback */}
                    <Route path="*"                   element={<Navigate to="/" replace />} />
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
