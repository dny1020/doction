import React from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth.jsx'
import { useI18n } from './i18n.jsx'
import Layout from './components/Layout.jsx'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
import Reader from './pages/Reader.jsx'
import Editor from './pages/Editor.jsx'
import History from './pages/History.jsx'
import Settings from './pages/Settings.jsx'
import Trash from './pages/Trash.jsx'

// Envuelve las rutas que requieren sesión. Mientras se comprueba la sesión inicial
// muestra un placeholder; si no hay usuario, redirige al login.
function RequireAuth({ children }) {
  const { user, loading } = useAuth()
  const { t } = useI18n()
  if (loading) return <div className="placeholder">{t('loading')}</div>
  if (!user) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  const { user, loading } = useAuth()

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
      <Route path="/register" element={user ? <Navigate to="/" replace /> : <Register />} />

      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Reader />} />
        <Route path="/new" element={<Editor mode="new" />} />
        <Route path="/p/:slug" element={<Reader />} />
        <Route path="/p/:slug/edit" element={<Editor mode="edit" />} />
        <Route path="/p/:slug/history" element={<History />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/trash" element={<Trash />} />
      </Route>

      <Route path="*" element={<Navigate to={loading ? '/' : user ? '/' : '/login'} replace />} />
    </Routes>
  )
}
