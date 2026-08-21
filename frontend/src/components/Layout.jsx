import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { MoreHorizontal, PanelLeft } from 'lucide-react'
import { api } from '../api.js'
import { useI18n } from '../i18n.jsx'
import Sidebar from './Sidebar.jsx'
import CommandPalette from './CommandPalette.jsx'
import CaptureModal from './CaptureModal.jsx'
import KeyboardShortcuts from './KeyboardShortcuts.jsx'

// En móvil el sidebar es un cajón (drawer) que tapa el contenido: arranca cerrado
// y se cierra al navegar. En escritorio arranca como diga localStorage.
const MOBILE_QUERY = '(max-width: 820px)'

function isMobile() {
  return window.matchMedia(MOBILE_QUERY).matches
}

// Shell de la app autenticada: barra lateral + contenido. Carga el árbol de
// páginas una vez y lo comparte con las rutas hijas (vía el contexto del Outlet),
// junto con reloadPages() para refrescarlo tras crear/borrar.
export default function Layout() {
  const { t } = useI18n()
  const location = useLocation()
  const [pages, setPages] = useState([])
  // Distinguimos "no hay páginas" de "falló la carga": sin esto un error de red
  // se veía como un workspace vacío ("No pages yet"), que es mentira.
  const [pagesError, setPagesError] = useState(false)
  const [collapsed, setCollapsedState] = useState(
    () => isMobile() || localStorage.getItem('sidebar') === 'collapsed',
  )
  const [barMenuOpen, setBarMenuOpen] = useState(false)
  const barMenuRef = useRef(null)

  const setCollapsed = useCallback((value) => {
    setCollapsedState(value)
    if (!isMobile()) {
      try {
        localStorage.setItem('sidebar', value ? 'collapsed' : 'open')
      } catch {
        // localStorage bloqueado (modo privado): el estado solo dura la sesión.
      }
    }
  }, [])

  // La clase vive en <html> porque el CSS del design system la espera ahí
  // (`.sidebar-collapsed .sidebar`, overlay, toggle). Se limpia al desmontar (logout).
  useEffect(() => {
    document.documentElement.classList.toggle('sidebar-collapsed', collapsed)
  }, [collapsed])
  useEffect(() => () => document.documentElement.classList.remove('sidebar-collapsed'), [])

  // En móvil, navegar a otra página cierra el cajón.
  useEffect(() => {
    if (isMobile()) setCollapsed(true)
  }, [location.pathname, setCollapsed])

  // Navegar cierra también el menú "⋯" de la barra.
  useEffect(() => setBarMenuOpen(false), [location.pathname])

  useEffect(() => {
    function onDocClick(event) {
      if (barMenuRef.current && !barMenuRef.current.contains(event.target)) setBarMenuOpen(false)
    }
    document.addEventListener('click', onDocClick)
    return () => document.removeEventListener('click', onDocClick)
  }, [])

  const reloadPages = useCallback(() => {
    api
      .get('/api/pages')
      .then((list) => {
        setPages(list)
        setPagesError(false)
      })
      .catch(() => {
        setPages([])
        setPagesError(true)
      })
  }, [])

  useEffect(() => {
    reloadPages()
  }, [reloadPages])

  // El título y las acciones de la barra móvil salen de la URL, igual que el
  // resaltado del árbol en Sidebar.jsx: así la barra no necesita que cada ruta
  // le publique su estado.
  const routeMatch = location.pathname.match(/^\/p\/([^/]+)/)
  const activeSlug = routeMatch ? decodeURIComponent(routeMatch[1]) : null
  const activePage = activeSlug ? pages.find((p) => p.slug === activeSlug) : null
  // Las acciones solo tienen sentido en la vista de lectura, no editando ni en
  // el historial de esa misma página.
  const isReader = Boolean(activeSlug) && /^\/p\/[^/]+\/?$/.test(location.pathname)

  let barTitle = ''
  if (activePage) barTitle = activePage.title
  else if (location.pathname.startsWith('/notes')) barTitle = t('notes')
  else if (location.pathname.startsWith('/settings')) barTitle = t('settings')
  else if (location.pathname.startsWith('/trash')) barTitle = t('trash')
  else if (location.pathname.startsWith('/new')) barTitle = t('new_page')

  return (
    <div className="layout">
      <a className="skip-link" href="#content">
        {t('skip_to_content')}
      </a>
      <button
        className="sidebar-toggle sidebar-toggle--show"
        type="button"
        onClick={() => setCollapsed(false)}
        aria-label={t('show_sidebar')}
      >
        <PanelLeft size={16} />
      </button>
      <div className="sidebar-overlay" onClick={() => setCollapsed(true)} />
      <Sidebar
        pages={pages}
        pagesError={pagesError}
        onReload={reloadPages}
        onCollapse={() => setCollapsed(true)}
      />
      <main className="content" id="content">
        <div className="app-bar">
          <button
            className="sidebar-toggle"
            type="button"
            onClick={() => setCollapsed(false)}
            aria-label={t('show_sidebar')}
          >
            <PanelLeft size={16} />
          </button>
          <span className="app-bar-title">{barTitle}</span>
          {isReader && (
            <span className="app-bar-actions" ref={barMenuRef}>
              <button
                className="sidebar-toggle"
                type="button"
                aria-label={t('page_actions')}
                onClick={() => setBarMenuOpen((v) => !v)}
              >
                <MoreHorizontal size={16} />
              </button>
              <div className={'avatar-menu' + (barMenuOpen ? ' open' : '')}>
                <Link className="avatar-menu-item" to={'/p/' + activeSlug + '/edit'}>
                  {t('edit')}
                </Link>
                <Link className="avatar-menu-item" to={'/new?parent=' + activeSlug}>
                  {t('new_subpage')}
                </Link>
                <Link className="avatar-menu-item" to={'/p/' + activeSlug + '/history'}>
                  {t('history')}
                </Link>
              </div>
            </span>
          )}
        </div>
        <div className="content-body">
          <Outlet context={{ pages, pagesError, reloadPages }} />
        </div>
      </main>
      <CommandPalette pages={pages} />
      <CaptureModal />
      <KeyboardShortcuts />
    </div>
  )
}
