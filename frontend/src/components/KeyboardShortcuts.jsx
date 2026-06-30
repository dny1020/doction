import React, { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useI18n } from '../i18n.jsx'

// Atajos de teclado globales + modal de ayuda (?). Equivale a los atajos del
// frontend Jinja, adaptados a las rutas de la SPA. (⌘K vive en CommandPalette.)
//   /  enfocar la búsqueda · e  editar la página actual · n  nueva página
//   ?  esta ayuda · Esc  cerrar la ayuda
export default function KeyboardShortcuts() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const location = useLocation()
  const [helpOpen, setHelpOpen] = useState(false)

  // Ruta actual en un ref para que el listener (montado una vez) la lea fresca.
  const locRef = useRef(location)
  locRef.current = location

  useEffect(() => {
    function onKey(event) {
      if (event.defaultPrevented) return

      // Esc cierra la ayuda (funciona incluso si el foco está en un campo).
      if (event.key === 'Escape') {
        setHelpOpen(false)
        return
      }

      // No disparar atajos mientras se escribe, ni pisar combos con modificadores (⌘K…).
      const el = event.target
      if (el && (el.isContentEditable || el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) return
      if (event.metaKey || event.ctrlKey || event.altKey) return

      if (event.key === '?') {
        event.preventDefault()
        setHelpOpen((open) => !open)
      } else if (event.key === 'e') {
        // Editar la página actual solo si estamos en su vista de lectura (/p/slug).
        const match = locRef.current.pathname.match(/^\/p\/([^/]+)$/)
        if (match) navigate('/p/' + match[1] + '/edit')
      } else if (event.key === 'n') {
        navigate('/new')
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
      onClick={(event) => {
        if (event.target === event.currentTarget) setHelpOpen(false)
      }}
    >
      <div className="shortcuts-modal" role="dialog" aria-modal="true" aria-label={t('shortcuts_title')}>
        <div className="shortcuts-head">
          <span className="shortcuts-title">{t('shortcuts_title')}</span>
          <button className="shortcuts-close" type="button" onClick={() => setHelpOpen(false)} aria-label={t('close')}>
            ×
          </button>
        </div>
        <ul className="shortcuts-list">
          <li><span>{t('sc_focus_search')}</span><span><kbd>/</kbd></span></li>
          <li><span>{t('sc_command_palette')}</span><span><kbd>⌘</kbd> <kbd>K</kbd></span></li>
          <li><span>{t('sc_edit')}</span><span><kbd>e</kbd></span></li>
          <li><span>{t('sc_new_page')}</span><span><kbd>n</kbd></span></li>
          <li><span>{t('sc_help')}</span><span><kbd>?</kbd></span></li>
          <li><span>{t('sc_close')}</span><span><kbd>Esc</kbd></span></li>
        </ul>
      </div>
    </div>
  )
}
