import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import RequireAuth from './components/RequireAuth';
import Sidebar from './components/Sidebar'; // Import Sidebar component

// Import các trang của bạn
import Login from './pages/Login';
import Overview from './pages/Overview';
import Alerts from './pages/Alerts';
import Firewall from './pages/Firewall';
import ServerManagement from './pages/ServerManagement';
import NotificationSettings from './pages/NotificationSettings';
import ProfileSettings from './pages/ProfileSettings'; // Import ProfileSettings
import GeoBlocking from './pages/GeoBlocking'; // Import GeoBlocking
import UserManagement from './pages/UserManagement'; // Import UserManagement
import LogViewer from './pages/LogViewer';
import AuditLogs from './pages/AuditLogs';
import AIInsights from './pages/AIInsights';
import Network from './pages/Network';
import Reports from './pages/Reports';
import Register from './pages/Register';


export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        
        {/* Protected Routes */}
        <Route 
          path="/*" 
          element={
            <RequireAuth>
              <div className="flex min-h-screen bg-gray-900 text-gray-200">
                <Sidebar /> {/* Render Sidebar */}
                <div className="flex-1 p-6">
                  <Routes>
                    <Route index element={<Overview />} />
                    <Route path="alerts" element={<Alerts />} />
                    <Route path="firewall" element={<Firewall />} />
                    <Route path="servers" element={<ServerManagement />} />
                    <Route path="settings/notifications" element={<NotificationSettings />} />
                    <Route path="settings/profile" element={<ProfileSettings />} /> {/* New Route */}
                    <Route path="geo-blocking" element={<GeoBlocking />} /> {/* New Route for FR04 */}
                    <Route path="settings/users" element={<UserManagement />} /> {/* New Route for FR01 */}
                    <Route path="ai-insights" element={<AIInsights />} />
                    <Route path="network" element={<Network />} />
                    <Route path="logs" element={<LogViewer />} />
                    <Route path="audit" element={<AuditLogs />} />
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