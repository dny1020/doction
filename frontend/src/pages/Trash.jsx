import { useEffect, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { api } from '../api.js'
import { useI18n } from '../i18n.jsx'
import { ListSkeleton } from '../components/Skeleton.jsx'
import { useDocumentTitle } from '../useDocumentTitle.js'
import { useToast } from '../components/Toast.jsx'
import { useConfirm } from '../components/ConfirmDialog.jsx'

// The trash: soft-deleted pages, which can be restored or purged. Restoring refreshes
// the sidebar tree.
export default function Trash() {
  const { reloadPages } = useOutletContext()
  const { t } = useI18n()
  const toast = useToast()
  const confirm = useConfirm()
  const [items, setItems] = useState(null) // null = cargando
  const [busy, setBusy] = useState(null) // slug of the row with an action in flight
  useDocumentTitle(t('trash'), null)

  function reload() {
    api
      .get('/api/trash')
      .then(setItems)
      .catch(() => setItems([]))
  }
  useEffect(reload, [])

  // Restore and purge lock their own row while in flight: two quick clicks sent two
  // requests, and a purge does not come back.
  async function onRestore(slug) {
    if (busy) return
    setBusy(slug)
    try {
      await api.post('/api/trash/' + slug + '/restore')
    } catch (e) {
      toast(e.message, 'error')
      return
    } finally {
      setBusy(null)
    }
    reload()
    reloadPages()
  }

  async function onPurge(slug) {
    if (busy) return
    if (!(await confirm(t('confirm_purge'), { confirmLabel: t('delete_forever'), danger: true })))
      return
    setBusy(slug)
    try {
      await api.post('/api/trash/' + slug + '/purge')
    } catch (e) {
      toast(e.message, 'error')
      return
    } finally {
      setBusy(null)
    }
    reload()
  }

  if (items === null) return <ListSkeleton />

  return (
    <div className="settings">
      <h1 className="settings-h1">{t('trash')}</h1>
      <p className="card-desc">{t('trash_desc')}</p>

      {items.length > 0 ? (
        <ul className="rows rows--divided">
          {items.map((p) => (
            <li className="row" key={p.slug}>
              <div className="row-name">
                <span className="row-title">{p.title}</span>
                <span className="meta">{p.deleted_at ? p.deleted_at.slice(0, 10) : ''}</span>
              </div>
              <div className="row-actions">
                <button
                  className="btn"
                  type="button"
                  onClick={() => onRestore(p.slug)}
                  disabled={busy === p.slug}
                >
                  {t('restore')}
                </button>
                <button
                  className="btn btn-danger"
                  type="button"
                  onClick={() => onPurge(p.slug)}
                  disabled={busy === p.slug}
                >
                  {t('delete_forever')}
                </button>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <div className="placeholder">
          <h1>{t('trash_empty')}</h1>
        </div>
      )}
    </div>
  )
}
