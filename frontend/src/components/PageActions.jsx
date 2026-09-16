import { useEffect, useRef, useState } from 'react'
import { MoreHorizontal } from 'lucide-react'
import { useI18n } from '../i18n.jsx'
import { useToast } from './Toast.jsx'
import { api } from '../api.js'

// The "⋯" menu on each tree row: move and rename. Renaming leaves an alias so existing
// [[wikilinks]] keep resolving, which is what the save message says.
//
// A modal <dialog> rather than an absolute dropdown: the tree scrolls, and a dropdown
// anchored to a row clipped against .page-list's edge near the bottom.
export default function PageActions({ page, pages, onDone, tabIndex }) {
  const { t } = useI18n()
  const toast = useToast()
  const [dialog, setDialog] = useState(null) // 'menu' | 'move' | 'rename' | null
  const [value, setValue] = useState('')
  const dialogRef = useRef(null)

  useEffect(() => {
    const el = dialogRef.current
    if (dialog && el && !el.open) el.showModal()
    if (!dialog && el && el.open) el.close()
  }, [dialog])

  function openDialog(kind) {
    setValue(kind === 'rename' ? page.slug : '')
    setDialog(kind)
  }

  // The <dialog> fills the screen, so a click "outside" lands on the element itself
  // rather than on its content.
  function onDialogClick(event) {
    if (event.target === dialogRef.current) setDialog(null)
  }

  async function submit(event) {
    event.preventDefault()
    try {
      if (dialog === 'rename') {
        await api.post('/api/pages/' + page.slug + '/rename', { slug: value })
        toast(t('msg_renamed'))
      } else {
        await api.post('/api/pages/' + page.slug + '/move', { parent_slug: value || null })
        toast(t('msg_moved'))
      }
      setDialog(null)
      onDone?.()
    } catch (e) {
      toast(e.message, 'error')
    }
  }

  // A parent cannot be the page itself; the backend also rejects cycles.
  const targets = pages.filter((p) => p.slug !== page.slug)

  return (
    <span className="page-row-actions">
      <button
        className="page-row-actions-btn"
        type="button"
        tabIndex={tabIndex}
        aria-label={t('page_actions')}
        title={t('page_actions')}
        onClick={(e) => {
          e.preventDefault()
          e.stopPropagation()
          setDialog('menu')
        }}
      >
        <MoreHorizontal size={14} />
      </button>

      <dialog
        ref={dialogRef}
        className="confirm-dialog"
        onCancel={() => setDialog(null)}
        onClick={onDialogClick}
      >
        {dialog === 'menu' && (
          <div className="row-menu">
            <p className="confirm-dialog-msg">{page.title}</p>
            <button className="avatar-menu-item" type="button" onClick={() => openDialog('move')}>
              {t('move')}
            </button>
            <button className="avatar-menu-item" type="button" onClick={() => openDialog('rename')}>
              {t('rename')}
            </button>
          </div>
        )}

        {(dialog === 'move' || dialog === 'rename') && (
          <form onSubmit={submit}>
            <p className="confirm-dialog-msg">
              {dialog === 'rename' ? t('rename_to') : t('move_to')}
            </p>
            {dialog === 'rename' ? (
              <input
                className="field"
                autoFocus
                value={value}
                onChange={(e) => setValue(e.target.value)}
              />
            ) : (
              <select className="field" value={value} onChange={(e) => setValue(e.target.value)}>
                <option value="">{t('move_to_root')}</option>
                {targets.map((p) => (
                  <option key={p.slug} value={p.slug}>
                    {p.title}
                  </option>
                ))}
              </select>
            )}
            <div className="confirm-dialog-actions">
              <button className="btn" type="button" onClick={() => setDialog(null)}>
                {t('cancel')}
              </button>
              <button className="btn btn-primary" type="submit">
                {t('save')}
              </button>
            </div>
          </form>
        )}
      </dialog>
    </span>
  )
}
