import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, Outlet, useLocation, useParams } from 'react-router-dom'
import { MoreHorizontal, PanelLeft } from 'lucide-react'
import { api, setWorkspace } from '../api.js'
import { useAuth } from '../auth.jsx'
import { useI18n } from '../i18n.jsx'
import { newPagePath, pagePath } from '../routes.js'
import NotFound from '../pages/NotFound.jsx'
import Sidebar from './Sidebar.jsx'
import CommandPalette from './CommandPalette.jsx'
import ConnectionStatus from './ConnectionStatus.jsx'
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
  const { user } = useAuth()
  const params = useParams()

  // El workspace sale de la URL. Las rutas que no son de contenido (/settings) no
  // lo llevan, y ahí vale el de la última visita: el shell siempre necesita uno
  // para pintar el árbol.
  const active = user && user.active_workspace
  const fallback = active
    ? active.slug
    : user && user.workspaces.length > 0
      ? user.workspaces[0].slug
      : null
  // Que no exista y que no sea tuyo se responden igual: el cliente solo conoce
  // sus propias membresías, así que no hay forma de distinguirlos desde aquí.
  const unknownWs =
    Boolean(params.ws) && !(user || { workspaces: [] }).workspaces.some((w) => w.slug === params.ws)
  const ws = unknownWs ? fallback : params.ws || fallback

  // Se fija durante el render y no en un efecto a propósito: los efectos de los
  // hijos corren antes que los del padre, así que un efecto aquí llegaría tarde y
  // el primer fetch de cada vista saldría con el workspace anterior.
  if (ws) setWorkspace(ws)

  const [pages, setPages] = useState([])
  // De qué workspace es el árbol que hay cargado. Sin esto, al cambiar de
  // workspace el árbol del anterior seguía en pie hasta que llegara el nuevo, y
  // la ruta /w/<ws> a secas redirigía a la primera página de ese árbol viejo —
  // una página que no existe en el workspace al que acabas de entrar.
  const [pagesWs, setPagesWs] = useState(null)
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
    // Sin workspace no hay árbol que pedir, y `api` no sabría a cuál preguntar.
    if (!ws) return
    api
      .get('/api/pages')
      .then((list) => {
        setPages(list)
        setPagesWs(ws)
        setPagesError(false)
      })
      .catch(() => {
        setPages([])
        setPagesWs(ws)
        setPagesError(true)
      })
    // El árbol es de un workspace: sin `ws` aquí, cambiar de workspace dejaba en
    // pantalla el árbol del anterior.
  }, [ws])

  useEffect(() => {
    reloadPages()
  }, [reloadPages])

  // El título y las acciones de la barra móvil salen de la URL, igual que el
  // resaltado del árbol en Sidebar.jsx: así la barra no necesita que cada ruta
  // le publique su estado.
  const activeSlug = params.slug || null
  const activePage = activeSlug ? pages.find((p) => p.slug === activeSlug) : null
  // Las acciones solo tienen sentido en la vista de lectura, no editando ni en
  // el historial de esa misma página.
  const isReader = Boolean(activeSlug) && /\/p\/[^/]+\/?$/.test(location.pathname)

  // Las rutas de contenido cuelgan del workspace (/w/<ws>/notes), así que el
  // título de la barra mira el final del path y no su principio.
  const tail = location.pathname.replace(/\/$/, '').split('/').pop()
  let barTitle = ''
  if (activePage) barTitle = activePage.title
  else if (location.pathname.startsWith('/settings')) barTitle = t('settings')
  else if (tail === 'notes') barTitle = t('notes')
  else if (tail === 'trash') barTitle = t('trash')
  else if (tail === 'new') barTitle = t('new_page')

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
        ws={ws}
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
                <Link className="avatar-menu-item" to={pagePath(ws, activeSlug, '/edit')}>
                  {t('edit')}
                </Link>
                <Link className="avatar-menu-item" to={newPagePath(ws, activeSlug)}>
                  {t('new_subpage')}
                </Link>
                <Link className="avatar-menu-item" to={pagePath(ws, activeSlug, '/history')}>
                  {t('history')}
                </Link>
              </div>
            </span>
          )}
        </div>
        <div className="content-body">
          {/* El workspace de la URL no existe: el 404 va dentro del shell, con la
              barra lateral del workspace propio, para no dejar a nadie en una
              pantalla sin salida. */}
          {unknownWs ? (
            <NotFound />
          ) : (
            <Outlet context={{ ws, pages, pagesReady: pagesWs === ws, pagesError, reloadPages }} />
          )}
        </div>
      </main>
      {/* Fuera de .app-bar: esa barra solo existe por debajo de 820px, así que ahí
          el indicador era invisible en escritorio. Va fijo sobre el shell, y como
          se calla cuando todo va bien, no ocupa nada la mayor parte del tiempo. */}
      <ConnectionStatus />
      <CommandPalette ws={ws} pages={pages} />
      <CaptureModal />
      <KeyboardShortcuts ws={ws} />
    </div>
  )
}
