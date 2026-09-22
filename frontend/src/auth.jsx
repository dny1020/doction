import { createContext, useContext, useEffect, useState } from 'react'
import { api } from './api.js'

// Auth context: holds the current user from /api/me and exposes login/register/logout.

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null) // the /api/me object, or null when signed out
  const [loading, setLoading] = useState(true) // true while the initial session is checked

  // On start, try to load the user from the session cookie.
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
