import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useI18n } from '../i18n.jsx'
import { pagePath } from '../routes.js'

// Command palette (⌘K / Ctrl-K): jump to any page by title, keyboard-navigable.
export default function CommandPalette({ ws, pages }) {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [sel, setSel] = useState(0) // índice resaltado dentro de los resultados
  const inputRef = useRef(null)
  const prevFocusRef = useRef(null) // a quién devolver el foco al cerrar

  // Pages whose title contains the query, up to 50; an empty query lists them all.
  const matches = useMemo(() => {
    const q = query.trim().toLowerCase()
    return pages.filter((p) => p.title.toLowerCase().includes(q)).slice(0, 50)
  }, [pages, query])

  // ⌘K / Ctrl-K toggles from anywhere; Esc closes even with focus outside the input.
  useEffect(() => {
    function onKey(event) {
      // Without Shift: ⌘⇧K is quick capture, and since `event.key` arrives as an
      // uppercase 'K' this opened both, one on top of the other.
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

  // On open: clear the query, highlight the first result, focus the input. On close:
  // return focus to where it was.
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

  // Keys inside the input: arrows to move, Enter to open, Esc to close.
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
      // Closed it stays in the DOM at opacity:0, so `inert` keeps its input out of the
      // tab order inside an aria-hidden subtree.
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
