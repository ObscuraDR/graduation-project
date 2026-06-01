import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import RequireAuth from './components/RequireAuth'
import Login from './pages/Login'
import Overview from './pages/Overview'
import Alerts from './pages/Alerts'
import Traffic from './pages/Traffic'
import Network from './pages/Network'
import AIInsights from './pages/AIInsights'
import Settings from './pages/Settings'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route index element={<Overview />} />
          <Route path="alerts" element={<Alerts />} />
          <Route path="traffic" element={<Traffic />} />
          <Route path="network" element={<Network />} />
          <Route path="ai-insights" element={<AIInsights />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
