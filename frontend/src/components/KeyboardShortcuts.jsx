import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useI18n } from '../i18n.jsx'
import { newPagePath, pagePath } from '../routes.js'

// Global keyboard shortcuts plus the help modal. (⌘K lives in CommandPalette.)
//   /  focus search · e  edit the current page · n  new page
//   ?  this help · Esc  close it
export default function KeyboardShortcuts({ ws }) {
  const { t } = useI18n()
  const navigate = useNavigate()
  const location = useLocation()
  const [helpOpen, setHelpOpen] = useState(false)
  const closeRef = useRef(null)
  const prevFocusRef = useRef(null) // where to return focus on close

  // Ruta actual en un ref para que el listener (montado una vez) la lea fresca.
  const locRef = useRef(location)
  locRef.current = location
  const wsRef = useRef(ws)
  wsRef.current = ws

  // On open, focus the close button; on close, return focus to where it was.
  useEffect(() => {
    if (helpOpen) {
      prevFocusRef.current = document.activeElement
      closeRef.current?.focus()
    } else if (prevFocusRef.current) {
      prevFocusRef.current.focus?.()
      prevFocusRef.current = null
    }
  }, [helpOpen])

  useEffect(() => {
    function onKey(event) {
      if (event.defaultPrevented) return

      // Esc closes the help, even with focus in a field.
      if (event.key === 'Escape') {
        setHelpOpen(false)
        return
      }

      // No disparar atajos mientras se escribe, ni pisar combos con modificadores (⌘K…).
      const el = event.target
      if (el && (el.isContentEditable || el.tagName === 'INPUT' || el.tagName === 'TEXTAREA'))
        return
      if (event.metaKey || event.ctrlKey || event.altKey) return

      if (event.key === '?') {
        event.preventDefault()
        setHelpOpen((open) => !open)
      } else if (event.key === 'e') {
        // Edit the current page only from its reading view.
        const match = locRef.current.pathname.match(/\/p\/([^/]+)$/)
        if (match) navigate(pagePath(wsRef.current, match[1], '/edit'))
      } else if (event.key === 'n') {
        navigate(newPagePath(wsRef.current))
      } else if (event.key === '/') {
        event.preventDefault()
        const search = document.getElementById('sidebar-search')
        if (search) search.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [navigate])

  return (
    <div
      className={'shortcuts-overlay' + (helpOpen ? ' open' : '')}
      aria-hidden={helpOpen ? 'false' : 'true'}
      // Closed it stays in the DOM at opacity:0, so `inert` takes it out of the tab order.
      {...(helpOpen ? {} : { inert: '' })}
      onClick={(event) => {
        if (event.target === event.currentTarget) setHelpOpen(false)
      }}
    >
      <div
        className="shortcuts-modal"
        role="dialog"
        aria-modal="true"
        aria-label={t('shortcuts_title')}
      >
        <div className="shortcuts-head">
          <span className="shortcuts-title">{t('shortcuts_title')}</span>
          <button
            ref={closeRef}
            className="shortcuts-close"
            type="button"
            onClick={() => setHelpOpen(false)}
            aria-label={t('close')}
          >
            ×
          </button>
        </div>
        <ul className="shortcuts-list">
          <li>
            <span>{t('sc_focus_search')}</span>
            <span>
              <kbd>/</kbd>
            </span>
          </li>
          <li>
            <span>{t('sc_command_palette')}</span>
            <span>
              <kbd>⌘</kbd> <kbd>K</kbd>
            </span>
          </li>
          <li>
            <span>{t('sc_edit')}</span>
            <span>
              <kbd>e</kbd>
            </span>
          </li>
          <li>
            <span>{t('sc_new_page')}</span>
            <span>
              <kbd>n</kbd>
            </span>
          </li>
          <li>
            <span>{t('sc_help')}</span>
            <span>
              <kbd>?</kbd>
            </span>
          </li>
          <li>
            <span>{t('sc_close')}</span>
            <span>
              <kbd>Esc</kbd>
            </span>
          </li>
        </ul>
      </div>
    </div>
  )
}
