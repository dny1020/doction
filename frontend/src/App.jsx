import React from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth.jsx'
import Layout from './components/Layout.jsx'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
import Reader from './pages/Reader.jsx'
import Editor from './pages/Editor.jsx'

// Envuelve las rutas que requieren sesión. Mientras se comprueba la sesión inicial
// muestra un placeholder; si no hay usuario, redirige al login.
function RequireAuth({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="placeholder">Loading…</div>
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
      </Route>

      <Route path="*" element={<Navigate to={loading ? '/' : user ? '/' : '/login'} replace />} />
    </Routes>
  )
}
