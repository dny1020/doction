import { useCallback, useEffect, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import { api } from '../api.js'
import { useI18n } from '../i18n.jsx'
import { ListSkeleton } from '../components/Skeleton.jsx'
import { useDocumentTitle } from '../useDocumentTitle.js'
import { pagePath } from '../routes.js'
import { useToast } from '../components/Toast.jsx'

const PAGE_SIZE = 25

// Bandeja: feed cronológico de las capturas (`type: memo`). Va aparte del árbol
// a propósito — el árbol no pagina y la captura rápida crece sin límite — y se
// pagina por cursor sobre created_at.
export default function Notes() {
  const { ws } = useOutletContext()
  const { t } = useI18n()
  const toast = useToast()
  const [items, setItems] = useState(null) // null = cargando
  const [done, setDone] = useState(false)

  useDocumentTitle(t('notes'), ws)

  const load = useCallback(
    (before) => {
      const url =
        '/api/notes?limit=' + PAGE_SIZE + (before ? '&before=' + encodeURIComponent(before) : '')
      api
        .get(url)
        .then((batch) => {
          setItems((prev) => (before && prev ? prev.concat(batch) : batch))
          if (batch.length < PAGE_SIZE) setDone(true)
        })
        .catch((e) => {
          toast(e.message, 'error')
          setItems((prev) => prev || [])
        })
    },
    [toast],
  )

  useEffect(() => {
    load()
  }, [load])

  if (items === null) return <ListSkeleton />

  return (
    <div className="settings">
      <h1 className="settings-h1">{t('notes')}</h1>

      {items.length > 0 ? (
        <>
          <ul className="results">
            {items.map((n) => (
              <li key={n.slug}>
                <Link to={pagePath(ws, n.slug)}>{n.title}</Link>
                <p className="snippet">{n.excerpt}</p>
                <p className="subpage-date">{n.created_at?.slice(0, 10)}</p>
              </li>
            ))}
          </ul>
          {!done && (
            <button
              className="btn"
              type="button"
              onClick={() => load(items[items.length - 1].created_at)}
            >
              {t('load_more')}
            </button>
          )}
        </>
      ) : (
        <p className="muted">{t('no_notes')}</p>
      )}
    </div>
  )
}
