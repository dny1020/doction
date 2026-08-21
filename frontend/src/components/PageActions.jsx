import { useEffect, useRef, useState } from 'react'
import { MoreHorizontal } from 'lucide-react'
import { useI18n } from '../i18n.jsx'
import { useToast } from './Toast.jsx'
import { api } from '../api.js'

// Menú "⋯" de cada página del árbol: mover y renombrar.
//
// Mover es una sola llamada; el repo git es plano, así que reparentar no mueve
// ningún fichero. Renombrar deja alias del slug anterior, de modo que los
// [[wikilinks]] ya escritos siguen resolviendo — de ahí el mensaje al guardar.
//
// El menú es un <dialog> modal, no un desplegable absoluto: el árbol tiene su
// propio scroll, y un desplegable colgado de la fila se recortaba contra el
// borde de .page-list en cuanto la fila quedaba cerca del final visible.
export default function PageActions({ page, pages, onDone }) {
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

  // Clic en el backdrop: el <dialog> ocupa toda la pantalla, así que un clic
  // "fuera" llega al propio elemento y no a su contenido.
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

  // Un padre no puede ser la propia página; el backend además rechaza ciclos.
  const targets = pages.filter((p) => p.slug !== page.slug)

  return (
    <span className="page-row-actions">
      <button
        className="page-row-actions-btn"
        type="button"
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
                className="settings-input"
                autoFocus
                value={value}
                onChange={(e) => setValue(e.target.value)}
              />
            ) : (
              <select
                className="settings-input"
                value={value}
                onChange={(e) => setValue(e.target.value)}
              >
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
