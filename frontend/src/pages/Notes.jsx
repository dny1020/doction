import { useCallback, useEffect, useState } from 'react'
import { Link, useOutletContext } from 'react-router'
import { api, saveCapture } from '../api.js'
import { useI18n } from '../i18n.jsx'
import { ListSkeleton } from '../components/Skeleton.jsx'
import EmptyState from '../components/EmptyState.jsx'
import { useDocumentTitle } from '../useDocumentTitle.js'
import { pagePath } from '../routes.js'
import { useToast } from '../components/Toast.jsx'

const PAGE_SIZE = 25

// The inbox: a chronological feed of captures (`type: memo`), cursor-paginated on
// created_at. Separate from the tree on purpose, since the tree does not paginate and
// quick capture grows without bound.
export default function Notes() {
  const { ws, notesVersion } = useOutletContext()
  const { t } = useI18n()
  const toast = useToast()
  const [items, setItems] = useState(null) // null = loading
  const [done, setDone] = useState(false)
  // The first page failing is not an empty inbox: a dead network must not say "nothing
  // captured yet".
  const [loadError, setLoadError] = useState(null)
  const [text, setText] = useState('')
  const [saving, setSaving] = useState(false)

  useDocumentTitle(t('notes'), ws)

  const load = useCallback(
    (before) => {
      const url =
        '/api/notes?limit=' + PAGE_SIZE + (before ? '&before=' + encodeURIComponent(before) : '')
      api
        .get(url)
        .then((batch) => {
          setItems((prev) => (before && prev ? prev.concat(batch) : batch))
          setDone(batch.length < PAGE_SIZE)
          setLoadError(null)
        })
        .catch((e) => {
          // A failed "load more" keeps what is already listed; a failed first page (or
          // refresh) replaces the list, since showing it would claim it is current.
          if (before) toast(e.message, 'error')
          else setLoadError(e)
        })
    },
    [toast],
  )

  // ⌘⇧K anywhere bumps `notesVersion`, so a capture shows up here without a reload.
  useEffect(() => {
    load()
  }, [load, notesVersion])

  async function save(event) {
    event.preventDefault()
    const body = text.trim()
    if (!body || saving) return
    setSaving(true)
    try {
      await saveCapture(body)
      setText('')
      toast(t('capture_saved'))
      load()
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  function onKeyDown(event) {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') save(event)
  }

  let list
  if (loadError) {
    list = (
      <div className="placeholder placeholder--error" role="alert">
        <h1>{t('notes_load_error')}</h1>
        <p className="muted">{loadError.message}</p>
        <button className="btn btn-primary" type="button" onClick={() => load()}>
          {t('retry')}
        </button>
      </div>
    )
  } else if (items === null) {
    list = <ListSkeleton />
  } else if (items.length > 0) {
    list = (
      <>
        <ul className="rows notes-list">
          {items.map((n) => (
            <li className="row" key={n.slug}>
              <div className="row-name">
                <Link to={pagePath(ws, n.slug)}>{n.title}</Link>
                {/* A capture's title is its first line, so a short note's excerpt would repeat it. */}
                {n.excerpt && n.excerpt !== n.title && <p className="snippet">{n.excerpt}</p>}
              </div>
              <span className="meta">{n.created_at?.slice(0, 10)}</span>
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
    )
  } else {
    list = <EmptyState title={t('no_notes')} hint={t('notes_desc')} />
  }

  return (
    <div className="settings">
      <h1 className="settings-h1">{t('notes')}</h1>
      <p className="card-desc">{t('notes_desc')}</p>

      <form className="notes-capture" onSubmit={save}>
        <textarea
          className="field capture-input"
          rows={3}
          aria-label={t('capture')}
          placeholder={t('capture_placeholder')}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <div className="capture-actions">
          <span className="muted">{t('capture_hint')}</span>
          <button
            className="btn btn-primary btn-sm"
            type="submit"
            disabled={saving || !text.trim()}
          >
            {t('save')}
          </button>
        </div>
      </form>

      {list}
    </div>
  )
}
