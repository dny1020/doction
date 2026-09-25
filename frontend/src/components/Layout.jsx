import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, Outlet, useLocation, useParams } from 'react-router-dom'
import { MoreHorizontal, PanelLeft } from 'lucide-react'
import { api, isAbort, setWorkspace } from '../api.js'
import { useAuth } from '../auth.jsx'
import { useI18n } from '../i18n.jsx'
import { newPagePath, pagePath } from '../routes.js'
import NotFound from '../pages/NotFound.jsx'
import Sidebar from './Sidebar.jsx'
import CommandPalette from './CommandPalette.jsx'
import ConnectionStatus from './ConnectionStatus.jsx'
import CaptureModal from './CaptureModal.jsx'
import KeyboardShortcuts from './KeyboardShortcuts.jsx'

// On mobile the sidebar is a drawer over the content: closed on arrival, closed on
// navigation. On desktop it starts as localStorage says.
const MOBILE_QUERY = '(max-width: 820px)'

function isMobile() {
  return window.matchMedia(MOBILE_QUERY).matches
}

// Shell of the authenticated app. Loads the page tree once and shares it with the child
// routes through the Outlet context, along with reloadPages().
export default function Layout() {
  const { t } = useI18n()
  const location = useLocation()
  const { user } = useAuth()
  const params = useParams()

  // The workspace comes from the URL. Non-content routes (/settings) carry none, so the
  // last visited one is used: the shell always needs one to paint the tree.
  const active = user && user.active_workspace
  const fallback = active
    ? active.slug
    : user && user.workspaces.length > 0
      ? user.workspaces[0].slug
      : null
  // Missing and not-yours answer the same; the client only knows its own memberships.
  const unknownWs =
    Boolean(params.ws) && !(user || { workspaces: [] }).workspaces.some((w) => w.slug === params.ws)
  const ws = unknownWs ? fallback : params.ws || fallback

  // Set during render and not in an effect: children's effects run before the parent's,
  // so an effect here would arrive late and each view's first fetch would use the old one.
  if (ws) setWorkspace(ws)

  const [pages, setPages] = useState([])
  // Which workspace the loaded tree belongs to. Without it, switching workspaces left the
  // old tree standing and bare /w/<ws> redirected to a page the new one does not have.
  const [pagesWs, setPagesWs] = useState(null)
  // "No pages" and "load failed" are distinguished: a network error showed as an empty
  // workspace, which is a lie.
  const [pagesError, setPagesError] = useState(false)
  const [collapsed, setCollapsedState] = useState(
    () => isMobile() || localStorage.getItem('sidebar') === 'collapsed',
  )
  const [barMenuOpen, setBarMenuOpen] = useState(false)
  const [titleOffscreen, setTitleOffscreen] = useState(false)
  const barMenuRef = useRef(null)

  const setCollapsed = useCallback((value) => {
    setCollapsedState(value)
    if (!isMobile()) {
      try {
        localStorage.setItem('sidebar', value ? 'collapsed' : 'open')
      } catch {
        // localStorage blocked (private mode): the state lasts only this session.
      }
    }
  }, [])

  // The class lives on <html> because the design system's CSS expects it there. Cleared
  // on unmount, which is logout.
  useEffect(() => {
    document.documentElement.classList.toggle('sidebar-collapsed', collapsed)
  }, [collapsed])
  useEffect(() => () => document.documentElement.classList.remove('sidebar-collapsed'), [])

  // On mobile, navigating closes the drawer.
  useEffect(() => {
    if (isMobile()) setCollapsed(true)
  }, [location.pathname, setCollapsed])

  // Navigating also closes the bar's "⋯" menu.
  useEffect(() => setBarMenuOpen(false), [location.pathname])

  useEffect(() => {
    function onDocClick(event) {
      if (barMenuRef.current && !barMenuRef.current.contains(event.target)) setBarMenuOpen(false)
    }
    document.addEventListener('click', onDocClick)
    return () => document.removeEventListener('click', onDocClick)
  }, [])

  const reloadPages = useCallback(() => {
    // With no workspace there is no tree to ask for, and `api` would not know whom.
    if (!ws) return undefined
    const controller = new AbortController()
    api
      .get('/api/pages', controller.signal)
      .then((list) => {
        setPages(list)
        setPagesWs(ws)
        setPagesError(false)
      })
      .catch((e) => {
        if (isAbort(e)) return
        setPages([])
        setPagesWs(ws)
        setPagesError(true)
      })
    return () => controller.abort()
    // The tree belongs to a workspace: without `ws` here, switching left the old one up.
  }, [ws])

  useEffect(() => reloadPages(), [reloadPages])

  // The mobile bar's title and actions come from the URL, like the tree highlight in
  // Sidebar.jsx, so no route has to publish its state to the bar.
  const activeSlug = params.slug || null
  const activePage = activeSlug ? pages.find((p) => p.slug === activeSlug) : null
  // The actions only make sense in the reading view, not while editing or in history.
  const isReader = Boolean(activeSlug) && /\/p\/[^/]+\/?$/.test(location.pathname)

  // Content routes hang off the workspace, so the title reads the end of the path.
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
        pagesReady={pagesWs === ws}
        pagesError={pagesError}
        onReload={reloadPages}
        onCollapse={() => setCollapsed(true)}
      />
      <main className="content" id="content">
        <div
          className={
            'app-bar' +
            (isReader ? ' app-bar--reader' : '') +
            (titleOffscreen ? ' app-bar--titled' : '')
          }
        >
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
          {/* Unknown workspace: the 404 renders inside the shell so there is a way out. */}
          {unknownWs ? (
            <NotFound />
          ) : (
            <Outlet
              context={{
                ws,
                pages,
                pagesReady: pagesWs === ws,
                pagesError,
                reloadPages,
                setTitleOffscreen,
              }}
            />
          )}
        </div>
      </main>
      {/* Fixed over the shell; it renders nothing while everything works. */}
      <ConnectionStatus />
      <CommandPalette ws={ws} pages={pages} />
      <CaptureModal />
      <KeyboardShortcuts ws={ws} />
    </div>
  )
}
