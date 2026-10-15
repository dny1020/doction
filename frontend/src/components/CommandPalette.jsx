import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { api, isAbort } from '../api.js'
import { useAuth } from '../auth.jsx'
import { useI18n } from '../i18n.jsx'
import { pagePath } from '../routes.js'
import { Snippet } from './Sidebar.jsx'

// Command palette (⌘K / Ctrl-K): title matches at once, then the same hybrid search the
// sidebar runs, for pages that only mention the query in their content.
export default function CommandPalette({ ws, pages }) {
  const { t } = useI18n()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState([]) // content results for the current query
  const [sel, setSel] = useState(0) // the highlighted index within the results
  const inputRef = useRef(null)
  const prevFocusRef = useRef(null) // where to return focus on close

  // Debounced and abortable like the sidebar search, so a slow answer for an older query
  // cannot land under a newer one. One letter matches too much content to be useful.
  useEffect(() => {
    setHits([])
    const q = query.trim()
    if (q.length < 2) return undefined
    const controller = new AbortController()
    const timer = setTimeout(() => {
      api
        .get('/api/search?mode=hybrid&q=' + encodeURIComponent(q), controller.signal)
        .then(setHits)
        .catch((e) => {
          if (!isAbort(e)) setHits([])
        })
    }, 200)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [query])

  // Titles containing the query first, then content hits not already listed; up to 50.
  // An empty query lists every page.
  const matches = useMemo(() => {
    const q = query.trim().toLowerCase()
    const byTitle = pages.filter((p) => p.title.toLowerCase().includes(q))
    const seen = new Set(byTitle.map((p) => p.slug))
    return byTitle.concat(hits.filter((h) => !seen.has(h.slug))).slice(0, 50)
  }, [pages, query, hits])

  // A late content answer must not leave the highlight past the end of the list.
  const active = Math.min(sel, Math.max(matches.length - 1, 0))
  const wsName = (user?.workspaces.find((w) => w.slug === ws) || {}).name || ''

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
      setSel((active + 1) % matches.length)
    } else if (event.key === 'ArrowUp' && matches.length) {
      event.preventDefault()
      setSel((active - 1 + matches.length) % matches.length)
    } else if (event.key === 'Enter' && matches[active]) {
      event.preventDefault()
      go(matches[active])
    }
  }

  return (
    <div
      className={'palette' + (open ? ' open' : '')}
      aria-hidden={open ? 'false' : 'true'}
      // Closed it stays in the DOM at opacity:0, so `inert` keeps its input out of the
      // tab order inside an aria-hidden subtree.
      inert={!open}
      onClick={(event) => {
        if (event.target === event.currentTarget) setOpen(false) // backdrop click
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
          placeholder={t('palette_placeholder').replace('{ws}', wsName)}
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
                  className={'palette-item' + (i === active ? ' active' : '')}
                  onMouseEnter={() => setSel(i)}
                  onClick={(e) => {
                    e.preventDefault()
                    go(p)
                  }}
                  href={'/app' + pagePath(ws, p.slug)}
                >
                  {p.title}
                  {/* Only content hits carry a snippet; a title match already shows why. */}
                  {(p.parts || p.snippet) && <Snippet parts={p.parts} text={p.snippet} />}
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
