import React, { createContext, useContext, useEffect, useState } from 'react'
import { api } from './api.js'

// Contexto de autenticación: guarda el usuario actual (datos de /api/me) y
// expone login/register/logout. Cualquier componente lo usa con useAuth().

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null) // objeto de /api/me, o null si no hay sesión
  const [loading, setLoading] = useState(true) // true mientras comprobamos la sesión inicial

  // Al arrancar, intenta cargar el usuario desde la cookie de sesión.
  useEffect(() => {
    api
      .get('/api/me')
      .then((me) => setUser(me))
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  async function login(email, password) {
    const me = await api.post('/api/auth/login', { email, password })
    setUser(me)
  }

  async function register(email, password) {
    const me = await api.post('/api/auth/register', { email, password })
    setUser(me)
  }

  async function logout() {
    await api.post('/api/auth/logout')
    setUser(null)
  }

  async function refresh() {
    const me = await api.get('/api/me')
    setUser(me)
  }

  const value = { user, loading, login, register, logout, refresh }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  return useContext(AuthContext)
}
