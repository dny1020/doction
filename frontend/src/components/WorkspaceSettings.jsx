import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { useI18n } from '../i18n.jsx'

// Sección de ajustes para los workspaces: crear uno nuevo y, para cada workspace
// propio, renombrarlo, exportarlo, borrarlo y gestionar sus miembros.
export default function WorkspaceSettings({ setFlash }) {
  const { user, refresh } = useAuth()
  const { t } = useI18n()
  const [newName, setNewName] = useState('')
  const [busy, setBusy] = useState(false)

  const workspaces = user.workspaces || []
  const ownedCount = workspaces.filter((w) => w.role === 'owner').length

  async function onCreate(event) {
    event.preventDefault()
    if (!newName.trim()) return
    setBusy(true)
    try {
      await api.post('/api/workspaces', { name: newName })
      setNewName('')
      await refresh()
      setFlash({ tone: 'ok', text: t('msg_ws_created') })
    } catch (e) {
      setFlash({ tone: 'error', text: e.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="settings-card">
      <h2 className="settings-card-title">{t('workspaces')}</h2>
      <p className="settings-card-desc">{t('workspaces_desc')}</p>

      <ul className="ws-manage">
        {workspaces.map((ws) => (
          <WorkspaceRow
            key={ws.slug}
            ws={ws}
            ownedCount={ownedCount}
            isActive={user.active_workspace && ws.slug === user.active_workspace.slug}
            setFlash={setFlash}
          />
        ))}
      </ul>

      <form className="token-add" onSubmit={onCreate}>
        <input
          className="settings-input"
          type="text"
          maxLength={60}
          placeholder={t('new_workspace')}
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
        />
        <button className="btn btn-primary" type="submit" disabled={busy}>{t('create')}</button>
      </form>
    </section>
  )
}

// Una fila de workspace. Si el usuario es owner, despliega la gestión completa
// (renombrar / exportar / borrar / miembros); si es member, solo exportar.
function WorkspaceRow({ ws, ownedCount, isActive, setFlash }) {
  const { refresh } = useAuth()
  const { t } = useI18n()
  const isOwner = ws.role === 'owner'
  const [name, setName] = useState(ws.name)

  async function onRename(event) {
    event.preventDefault()
    try {
      await api.put('/api/workspaces/' + ws.slug, { name })
      await refresh()
      setFlash({ tone: 'ok', text: t('msg_ws_renamed') })
    } catch (e) {
      setFlash({ tone: 'error', text: e.message })
    }
  }

  async function onDelete() {
    if (!window.confirm(t('confirm_delete_ws_a') + ' “' + ws.name + '” ' + t('confirm_delete_ws_b'))) return
    try {
      await api.del('/api/workspaces/' + ws.slug)
      if (isActive) {
        // Si borramos el activo, recargamos para re-arrancar con otro workspace.
        window.location.assign('/app/')
        return
      }
      await refresh()
      setFlash({ tone: 'ok', text: t('msg_ws_deleted') })
    } catch (e) {
      setFlash({ tone: 'error', text: e.message })
    }
  }

  return (
    <li>
      <details className="ws-item">
        <summary className="ws-summary">
          <span className="ws-summary-name">{ws.name}</span>
          <span className="member-role">{t(ws.role)}</span>
        </summary>
        <div className="ws-body">
          <div className="ws-manage-row">
            {isOwner && (
              <form className="ws-rename" onSubmit={onRename}>
                <input
                  className="settings-input"
                  type="text"
                  maxLength={60}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
                <button className="btn" type="submit">{t('rename')}</button>
              </form>
            )}
            <a className="btn" href={'/api/workspaces/' + ws.slug + '/export'}>{t('export')}</a>
            {isOwner && (
              <button
                className="btn btn-danger"
                type="button"
                onClick={onDelete}
                disabled={ownedCount <= 1}
                title={ownedCount <= 1 ? t('cannot_delete_only_ws') : undefined}
              >
                {t('delete')}
              </button>
            )}
          </div>
          {isOwner && <MemberList slug={ws.slug} setFlash={setFlash} />}
        </div>
      </details>
    </li>
  )
}

// Lista de miembros de un workspace (solo visible para el owner): añadir por email
// y quitar miembros que no sean el owner.
function MemberList({ slug, setFlash }) {
  const { t } = useI18n()
  const [members, setMembers] = useState([])
  const [email, setEmail] = useState('')

  function reload() {
    api.get('/api/workspaces/' + slug + '/members').then(setMembers).catch(() => setMembers([]))
  }
  useEffect(reload, [slug])

  async function onAdd(event) {
    event.preventDefault()
    try {
      await api.post('/api/workspaces/' + slug + '/members', { email })
      setEmail('')
      reload()
      setFlash({ tone: 'ok', text: t('msg_member_added') })
    } catch (e) {
      setFlash({ tone: 'error', text: e.message })
    }
  }

  async function onRemove(userId) {
    try {
      await api.del('/api/workspaces/' + slug + '/members/' + userId)
      reload()
      setFlash({ tone: 'ok', text: t('msg_member_removed') })
    } catch (e) {
      setFlash({ tone: 'error', text: e.message })
    }
  }

  return (
    <div className="ws-members">
      <ul className="member-list">
        {members.map((m) => (
          <li className="member-row" key={m.user_id}>
            <span className="member-id">{m.display_name || m.email}</span>
            <span className="member-role">{t(m.role)}</span>
            {m.role !== 'owner' && (
              <button className="btn btn-sm btn-danger" type="button" onClick={() => onRemove(m.user_id)}>
                {t('remove')}
              </button>
            )}
          </li>
        ))}
      </ul>
      <form className="member-add" onSubmit={onAdd}>
        <input
          className="settings-input"
          type="email"
          placeholder={t('member_email_ph')}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <button className="btn" type="submit">{t('add_member')}</button>
      </form>
    </div>
  )
}
