import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import MenuAnalysis from './pages/MenuAnalysis'
import ComboEngine from './pages/ComboEngine'
import VoiceOrder from './pages/VoiceOrder'

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        {/* Sidebar */}
        <aside className="sidebar">
          <div className="sidebar-brand">
            <h2>🍽️ Petpooja AI</h2>
            <p>Revenue & Voice Copilot</p>
          </div>
          <ul className="nav-links">
            <li>
              <NavLink to="/" end>
                <span className="nav-icon">📊</span> Dashboard
              </NavLink>
            </li>
            <li>
              <NavLink to="/menu-analysis">
                <span className="nav-icon">🎯</span> Menu Analysis
              </NavLink>
            </li>
            <li>
              <NavLink to="/combos">
                <span className="nav-icon">🔗</span> Combo Engine
              </NavLink>
            </li>
            <li>
              <NavLink to="/voice-order">
                <span className="nav-icon">🎙️</span> Voice Order
              </NavLink>
            </li>
          </ul>
        </aside>

        {/* Main Content */}
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/menu-analysis" element={<MenuAnalysis />} />
            <Route path="/combos" element={<ComboEngine />} />
            <Route path="/voice-order" element={<VoiceOrder />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
