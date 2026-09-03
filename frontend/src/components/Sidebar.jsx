import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  Check,
  ChevronsUpDown,
  Inbox,
  LogOut,
  Moon,
  PanelLeftClose,
  Plus,
  Search,
  Settings,
  Sun,
  Terminal,
  Trash2,
  X,
} from 'lucide-react'
import { useAuth } from '../auth.jsx'
import { useI18n } from '../i18n.jsx'
import { api } from '../api.js'
import { avatarColor, avatarLetter } from '../avatar.js'
import { getTheme, toggleTheme } from '../theme.js'
import { newPagePath, pagePath, wsPath } from '../routes.js'
import LanguageToggle from './LanguageToggle.jsx'
import PageTree from './PageTree.jsx'

// Barra lateral: marca, selector de workspace, búsqueda en vivo, árbol de páginas,
// botón de nueva página y, abajo, el cambio de tema + el menú de usuario.
export default function Sidebar({ ws, pages, pagesError, onReload, onCollapse }) {
  const { user, logout } = useAuth()
  const { t } = useI18n()
  const navigate = useNavigate()
  const params = useParams()

  const [query, setQuery] = useState('')
  const [results, setResults] = useState(null) // null = mostrar árbol; [] = sin resultados
  const [wsOpen, setWsOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [theme, setTheme] = useState(getTheme())

  const wsRef = useRef(null)
  const avatarRef = useRef(null)

  // slug de la página activa, sacado de la ruta, para resaltarla en el árbol.
  const activeSlug = params.slug || null

  // Búsqueda en vivo con un pequeño retardo, para no pegar a la API en cada tecla.
  useEffect(() => {
    const q = query.trim()
    if (!q) {
      setResults(null)
      return
    }
    const timer = setTimeout(() => {
      api
        .get('/api/search?mode=hybrid&q=' + encodeURIComponent(q))
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

  function switchWorkspace(slug) {
    setWsOpen(false)
    navigate(wsPath(slug))
    // El servidor guarda cuál fue el último para que una visita a `/` a secas
    // vuelva aquí. No se espera: quién manda es la URL, y si esto falla lo único
    // que se pierde es esa memoria.
    api.post('/api/workspaces/' + slug + '/switch').catch(() => {})
  }

  async function onLogout() {
    await logout()
    navigate('/login')
  }

  function onToggleTheme() {
    setTheme(toggleTheme())
  }

  const active = user ? user.workspaces.find((w) => w.slug === ws) : null
  const letter = user ? avatarLetter(user.display_name, user.email) : '?'

  return (
    <aside className="sidebar" aria-label="Sidebar">
      <div className="sidebar-head">
        <Link className="brand" to="/">
          <Terminal className="brand-icon lucide" size={20} />
          Doction
        </Link>
        <button
          className="sidebar-toggle"
          type="button"
          onClick={onCollapse}
          aria-label={t('hide_sidebar')}
          title={t('hide_sidebar')}
        >
          <PanelLeftClose size={16} />
        </button>
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
                    className={'ws-option' + (w.slug === ws ? ' active' : '')}
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
            id="sidebar-search"
            type="search"
            placeholder={t('search_placeholder')}
            autoComplete="off"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {query && (
            <button
              className="search-clear"
              type="button"
              onClick={() => setQuery('')}
              aria-label="Clear"
            >
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
                    <Link to={pagePath(ws, r.slug)} onClick={() => setQuery('')}>
                      {r.title}
                    </Link>
                    <Snippet parts={r.parts} text={r.snippet} />
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted no-results">
                {t('no_matches')} “{query}”.
              </p>
            )}
          </div>
        )}
      </div>

      {results === null && (
        <>
          <div className="sidebar-eyebrow">{t('pages')}</div>
          <nav className="page-list">
            {pagesError ? (
              <p className="muted">
                {t('tree_error')}{' '}
                <button className="btn btn-sm" type="button" onClick={onReload}>
                  {t('retry')}
                </button>
              </p>
            ) : pages.length > 0 ? (
              <PageTree ws={ws} pages={pages} activeSlug={activeSlug} onReload={onReload} />
            ) : (
              <p className="muted">{t('no_pages_yet')}</p>
            )}
          </nav>
        </>
      )}

      <div className="sidebar-foot">
        <Link className="inbox-link" to={wsPath(ws, '/notes')}>
          <Inbox className="lucide" size={15} /> {t('notes')}
        </Link>
        <Link className="new-btn" to={newPagePath(ws)}>
          <Plus className="lucide" size={15} /> {t('new_page')}
        </Link>
        <div className="sidebar-user">
          <div className="sidebar-controls">
            <LanguageToggle />
            <button
              className="theme-toggle"
              type="button"
              onClick={onToggleTheme}
              title={t('toggle_theme')}
            >
              {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
            </button>
          </div>
          <div className="avatar-wrap" ref={avatarRef}>
            <button
              className="avatar"
              type="button"
              onClick={() => setMenuOpen(!menuOpen)}
              title={user ? user.email : ''}
              style={user ? { background: avatarColor(user) } : undefined}
            >
              {letter}
            </button>
            <div className={'avatar-menu' + (menuOpen ? ' open' : '')}>
              {user && user.display_name && (
                <div className="avatar-menu-name">{user.display_name}</div>
              )}
              {user && <div className="avatar-menu-email">{user.email}</div>}
              <div className="avatar-menu-divider" />
              <Link className="avatar-menu-item" to="/settings" onClick={() => setMenuOpen(false)}>
                <Settings size={14} /> {t('settings')}
              </Link>
              <Link
                className="avatar-menu-item"
                to={wsPath(ws, '/trash')}
                onClick={() => setMenuOpen(false)}
              >
                <Trash2 size={14} /> {t('trash')}
              </Link>
              <div className="avatar-menu-divider" />
              <button className="avatar-menu-item" type="button" onClick={onLogout}>
                <LogOut size={14} /> {t('log_out')}
              </button>
            </div>
          </div>
        </div>
      </div>
    </aside>
  )
}

// El fragmento de un resultado llega ya partido en tramos por el servidor: los
// que coincidieron van en <mark> y el resto en texto. Antes esto era un
// dangerouslySetInnerHTML sobre el <mark> que ponía ts_headline, así que el
// cuerpo de la página entraba en el DOM como HTML — XSS almacenado con el
// renderer de markdown intacto. Nada del servidor vuelve a pintarse como markup.
function Snippet({ parts, text }) {
  if (!parts || parts.length === 0) return <p className="snippet">{text}</p>
  return (
    <p className="snippet">
      {parts.map((part, i) => (part.match ? <mark key={i}>{part.text}</mark> : part.text))}
    </p>
  )
}
