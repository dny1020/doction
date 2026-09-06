import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useI18n } from '../i18n.jsx'
import { pagePath } from '../routes.js'

// Paleta de comandos (⌘K / Ctrl-K): un buscador rápido para saltar a cualquier
// página por título, navegable con el teclado. Recibe el árbol de páginas del
// Layout. Reusa las clases `.palette*` del design system.
export default function CommandPalette({ ws, pages }) {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [sel, setSel] = useState(0) // índice resaltado dentro de los resultados
  const inputRef = useRef(null)
  const prevFocusRef = useRef(null) // a quién devolver el foco al cerrar

  // Resultados: páginas cuyo título contiene la búsqueda (máx. 50). Con la
  // búsqueda vacía se listan todas.
  const matches = useMemo(() => {
    const q = query.trim().toLowerCase()
    return pages.filter((p) => p.title.toLowerCase().includes(q)).slice(0, 50)
  }, [pages, query])

  // ⌘K / Ctrl-K abre o cierra la paleta desde cualquier parte de la app;
  // Esc la cierra aunque el foco esté fuera de su input.
  useEffect(() => {
    function onKey(event) {
      // Sin Shift: con él, ⌘⇧K es la captura rápida, y como `event.key` llega
      // como 'K' mayúscula esto abría las dos cosas, una encima de la otra.
      if (
        (event.metaKey || event.ctrlKey) &&
        !event.shiftKey &&
        (event.key === 'k' || event.key === 'K')
      ) {
        event.preventDefault()
        setOpen((isOpen) => !isOpen)
      } else if (event.key === 'Escape') {
        setOpen(false)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  // Al abrir, limpia la búsqueda, resalta el primero y enfoca el input; al
  // cerrar, devuelve el foco a donde estaba (a11y).
  useEffect(() => {
    if (open) {
      prevFocusRef.current = document.activeElement
      setQuery('')
      setSel(0)
      inputRef.current?.focus()
    } else if (prevFocusRef.current) {
      prevFocusRef.current.focus?.()
      prevFocusRef.current = null
    }
  }, [open])

  function go(page) {
    setOpen(false)
    navigate(pagePath(ws, page.slug))
  }

  // Teclas dentro del input: flechas para moverse, Enter para abrir, Esc para cerrar.
  function onInputKey(event) {
    if (event.key === 'Escape') {
      setOpen(false)
    } else if (event.key === 'ArrowDown' && matches.length) {
      event.preventDefault()
      setSel((i) => (i + 1) % matches.length)
    } else if (event.key === 'ArrowUp' && matches.length) {
      event.preventDefault()
      setSel((i) => (i - 1 + matches.length) % matches.length)
    } else if (event.key === 'Enter' && matches[sel]) {
      event.preventDefault()
      go(matches[sel])
    }
  }

  return (
    <div
      className={'palette' + (open ? ' open' : '')}
      aria-hidden={open ? 'false' : 'true'}
      // Cerrada queda en el DOM (solo opacity:0), así que `inert` evita que su
      // input siga siendo tabulable dentro de un subárbol aria-hidden.
      {...(open ? {} : { inert: '' })}
      onClick={(event) => {
        if (event.target === event.currentTarget) setOpen(false) // clic en el fondo
      }}
    >
      <div
        className="palette-box"
        role="dialog"
        aria-modal="true"
        aria-label={t('sc_command_palette')}
      >
        <input
          ref={inputRef}
          className="palette-input"
          type="text"
          autoComplete="off"
          placeholder={t('palette_placeholder')}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setSel(0)
          }}
          onKeyDown={onInputKey}
        />
        <ul className="palette-list">
          {matches.length > 0 ? (
            matches.map((p, i) => (
              <li key={p.slug}>
                <a
                  className={'palette-item' + (i === sel ? ' active' : '')}
                  onMouseEnter={() => setSel(i)}
                  onClick={(e) => {
                    e.preventDefault()
                    go(p)
                  }}
                  href={'/app' + pagePath(ws, p.slug)}
                >
                  {p.title}
                </a>
              </li>
            ))
          ) : (
            <li className="palette-empty">{t('palette_empty')}</li>
          )}
        </ul>
      </div>
    </div>
  )
}
