import React, { useEffect, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { api } from '../api.js'
import { useI18n } from '../i18n.jsx'

// Papelera: páginas borradas (soft-delete). Se pueden restaurar o borrar para
// siempre. Al restaurar refrescamos el árbol de la barra lateral.
export default function Trash() {
  const { reloadPages } = useOutletContext()
  const { t } = useI18n()
  const [items, setItems] = useState(null) // null = cargando

  function reload() {
    api.get('/api/trash').then(setItems).catch(() => setItems([]))
  }
  useEffect(reload, [])

  async function onRestore(slug) {
    await api.post('/api/trash/' + slug + '/restore')
    reload()
    reloadPages()
  }

  async function onPurge(slug) {
    if (!window.confirm(t('confirm_purge'))) return
    await api.post('/api/trash/' + slug + '/purge')
    reload()
  }

  if (items === null) return <div className="placeholder">{t('loading')}</div>

  return (
    <div className="settings">
      <h1 className="settings-h1">{t('trash')}</h1>
      <p className="settings-card-desc">{t('trash_desc')}</p>

      {items.length > 0 ? (
        <ul className="ws-manage">
          {items.map((p) => (
            <li className="ws-manage-item" key={p.slug}>
              <div className="ws-manage-row">
                <span className="ws-name-static">{p.title}</span>
                <span className="member-role">{p.deleted_at ? p.deleted_at.slice(0, 10) : ''}</span>
                <button className="btn" type="button" onClick={() => onRestore(p.slug)}>
                  {t('restore')}
                </button>
                <button className="btn btn-danger" type="button" onClick={() => onPurge(p.slug)}>
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
