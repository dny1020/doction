import React, { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Check, ChevronsUpDown, LogOut, Moon, Plus, Search, Sun, Terminal, X } from 'lucide-react'
import { useAuth } from '../auth.jsx'
import { api } from '../api.js'
import { getTheme, toggleTheme } from '../theme.js'

// Barra lateral: marca, selector de workspace, búsqueda en vivo, árbol de páginas,
// botón de nueva página y, abajo, el cambio de tema + el menú de usuario.
export default function Sidebar({ pages }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [query, setQuery] = useState('')
  const [results, setResults] = useState(null) // null = mostrar árbol; [] = sin resultados
  const [wsOpen, setWsOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [theme, setTheme] = useState(getTheme())

  const wsRef = useRef(null)
  const avatarRef = useRef(null)

  // slug de la página activa, sacado de la URL (/p/<slug>), para resaltarla.
  const routeMatch = location.pathname.match(/^\/p\/([^/]+)/)
  const activeSlug = routeMatch ? decodeURIComponent(routeMatch[1]) : null

  // Búsqueda en vivo con un pequeño retardo, para no pegar a la API en cada tecla.
  useEffect(() => {
    const q = query.trim()
    if (!q) {
      setResults(null)
      return
    }
    const timer = setTimeout(() => {
      api
        .get('/api/search?q=' + encodeURIComponent(q))
        .then(setResults)
        .catch(() => setResults([]))
    }, 200)
    return () => clearTimeout(timer)
  }, [query])

  // Cierra los menús desplegables al hacer clic fuera de ellos.
  useEffect(() => {
    function onDocClick(event) {
      if (wsRef.current && !wsRef.current.contains(event.target)) setWsOpen(false)
      if (avatarRef.current && !avatarRef.current.contains(event.target)) setMenuOpen(false)
    }
    document.addEventListener('click', onDocClick)
    return () => document.removeEventListener('click', onDocClick)
  }, [])

  async function switchWorkspace(slug) {
    setWsOpen(false)
    try {
      await api.post('/api/workspaces/' + slug + '/switch')
      // Recarga completa: re-arranca usuario, árbol y página activa con el nuevo workspace.
      window.location.assign('/app/')
    } catch (e) {
      // Si falla el cambio, dejamos todo como está.
    }
  }

  async function onLogout() {
    await logout()
    navigate('/login')
  }

  function onToggleTheme() {
    setTheme(toggleTheme())
  }

  const active = user ? user.active_workspace : null
  const avatarLetter = user ? (user.display_name || user.email || '?').charAt(0).toUpperCase() : '?'

  return (
    <aside className="sidebar" aria-label="Sidebar">
      <div className="sidebar-head">
        <Link className="brand" to="/">
          <Terminal className="brand-icon lucide" size={20} />
          Doction
        </Link>
      </div>

      {user && user.workspaces.length > 0 && (
        <div className="workspace-wrap">
          <div className="ws-select" ref={wsRef}>
            <button className="ws-trigger" type="button" onClick={() => setWsOpen(!wsOpen)}>
              <span className="ws-trigger-label">{active ? active.name : '—'}</span>
              <ChevronsUpDown className="ws-trigger-icon lucide" size={15} />
            </button>
            <div className={'ws-menu' + (wsOpen ? ' open' : '')}>
              <div className="ws-menu-list">
                {user.workspaces.map((w) => (
                  <button
                    key={w.slug}
                    type="button"
                    className={'ws-option' + (active && w.slug === active.slug ? ' active' : '')}
                    onClick={() => switchWorkspace(w.slug)}
                  >
                    <span className="ws-option-name">{w.name}</span>
                    <Check className="ws-option-check lucide" size={14} />
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="search-wrap">
        <div className="search-field">
          <Search className="lucide" size={15} />
          <input
            type="search"
            placeholder="Search…"
            autoComplete="off"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {query && (
            <button className="search-clear" type="button" onClick={() => setQuery('')} aria-label="Clear">
              <X size={14} />
            </button>
          )}
        </div>
        {results !== null && (
          <div id="search-results">
            {results.length > 0 ? (
              <ul className="results">
                {results.map((r) => (
                  <li key={r.slug}>
                    <Link to={'/p/' + r.slug} onClick={() => setQuery('')}>
                      {r.title}
                    </Link>
                    <p className="snippet" dangerouslySetInnerHTML={{ __html: r.snippet }} />
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted no-results">No pages match “{query}”.</p>
            )}
          </div>
        )}
      </div>

      {results === null && (
        <>
          <div className="sidebar-eyebrow">Pages</div>
          <nav className="page-list">
            <ul>
              {pages.length > 0 ? (
                pages.map((p) => (
                  <li key={p.slug}>
                    <Link
                      to={'/p/' + p.slug}
                      data-depth={p.depth}
                      className={p.slug === activeSlug ? 'active' : undefined}
                    >
                      {p.title}
                    </Link>
                  </li>
                ))
              ) : (
                <li className="muted">No pages yet.</li>
              )}
            </ul>
          </nav>
        </>
      )}

      <div className="sidebar-foot">
        <Link className="new-btn" to="/new">
          <Plus className="lucide" size={15} /> New page
        </Link>
        <div className="sidebar-user">
          <div className="sidebar-controls">
            <button className="theme-toggle" type="button" onClick={onToggleTheme} title="Toggle theme">
              {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
            </button>
          </div>
          <div className="avatar-wrap" ref={avatarRef}>
            <button
              className="avatar"
              type="button"
              onClick={() => setMenuOpen(!menuOpen)}
              title={user ? user.email : ''}
              style={user && user.avatar_color ? { background: user.avatar_color } : undefined}
            >
              {avatarLetter}
            </button>
            <div className={'avatar-menu' + (menuOpen ? ' open' : '')}>
              {user && user.display_name && <div className="avatar-menu-name">{user.display_name}</div>}
              {user && <div className="avatar-menu-email">{user.email}</div>}
              <div className="avatar-menu-divider" />
              <button className="avatar-menu-item" type="button" onClick={onLogout}>
                <LogOut size={14} /> Log out
              </button>
            </div>
          </div>
        </div>
      </div>
    </aside>
  )
}
