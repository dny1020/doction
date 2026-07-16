import { useCallback, useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { PanelLeft } from 'lucide-react'
import { api } from '../api.js'
import { useI18n } from '../i18n.jsx'
import Sidebar from './Sidebar.jsx'
import CommandPalette from './CommandPalette.jsx'
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
        <div className="content-body">
          <Outlet context={{ pages, pagesError, reloadPages }} />
        </div>
      </main>
      <CommandPalette pages={pages} />
      <KeyboardShortcuts />
    </div>
  )
}
