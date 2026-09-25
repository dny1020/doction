import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { APP_BASE } from '../config.js'
import { useAuth } from '../auth.jsx'
import { useI18n } from '../i18n.jsx'
import { useToast } from './Toast.jsx'
import { useConfirm } from './ConfirmDialog.jsx'

// Workspace settings: create one, and for each owned workspace rename, export, delete
// and manage its members.
export default function WorkspaceSettings() {
  const { user, refresh } = useAuth()
  const { t } = useI18n()
  const toast = useToast()
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
      toast(t('msg_ws_created'))
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card">
      <h2 className="card-title">{t('workspaces')}</h2>
      <p className="card-desc">{t('workspaces_desc')}</p>

      <ul className="rows">
        {workspaces.map((ws) => (
          <WorkspaceRow
            key={ws.slug}
            ws={ws}
            ownedCount={ownedCount}
            isActive={user.active_workspace && ws.slug === user.active_workspace.slug}
          />
        ))}
      </ul>

      <form className="add-form" onSubmit={onCreate}>
        <input
          className="field"
          type="text"
          maxLength={60}
          placeholder={t('new_workspace')}
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
        />
        <button className="btn btn-primary" type="submit" disabled={busy}>
          {t('create')}
        </button>
      </form>
    </section>
  )
}

// One workspace row: the full management for an owner, export only for a member.
function WorkspaceRow({ ws, ownedCount, isActive }) {
  const { refresh } = useAuth()
  const { t } = useI18n()
  const toast = useToast()
  const confirm = useConfirm()
  const isOwner = ws.role === 'owner'
  const [name, setName] = useState(ws.name)
  // Deleting a workspace takes all its pages, which is the most destructive thing here
  // and was the only one with no guard against a second click.
  const [busy, setBusy] = useState(false)

  async function onRename(event) {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    try {
      await api.put('/api/workspaces/' + ws.slug, { name })
      await refresh()
      toast(t('msg_ws_renamed'))
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  async function onDelete() {
    if (busy) return
    const message = t('confirm_delete_ws_a') + ' “' + ws.name + '” ' + t('confirm_delete_ws_b')
    if (!(await confirm(message, { confirmLabel: t('delete'), danger: true }))) return
    setBusy(true)
    try {
      await api.del('/api/workspaces/' + ws.slug)
      if (isActive) {
        // Deleting the active workspace reloads into another one.
        window.location.assign(APP_BASE + '/')
        return
      }
      await refresh()
      toast(t('msg_ws_deleted'))
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setBusy(false)
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
          <div className="ws-actions">
            {isOwner && (
              <form className="ws-rename" onSubmit={onRename}>
                <input
                  className="field"
                  type="text"
                  maxLength={60}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
                <button className="btn" type="submit" disabled={busy}>
                  {t('rename')}
                </button>
              </form>
            )}
            <a className="btn" href={'/api/workspaces/' + ws.slug + '/export'}>
              {t('export')}
            </a>
            {isOwner && (
              <button
                className="btn btn-danger"
                type="button"
                onClick={onDelete}
                disabled={busy || ownedCount <= 1}
                title={ownedCount <= 1 ? t('cannot_delete_only_ws') : undefined}
              >
                {t('delete')}
              </button>
            )}
          </div>
          {isOwner && <MemberList slug={ws.slug} />}
        </div>
      </details>
    </li>
  )
}

// A workspace's member list, visible to the owner only: add by email, remove anyone but
// the owner.
function MemberList({ slug }) {
  const { t } = useI18n()
  const toast = useToast()
  const [members, setMembers] = useState([])
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)

  function reload() {
    api
      .get('/api/workspaces/' + slug + '/members')
      .then(setMembers)
      .catch(() => setMembers([]))
  }
  useEffect(reload, [slug])

  async function onAdd(event) {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    try {
      await api.post('/api/workspaces/' + slug + '/members', { email })
      setEmail('')
      reload()
      toast(t('msg_member_added'))
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  async function onRemove(userId) {
    if (busy) return
    setBusy(true)
    try {
      await api.del('/api/workspaces/' + slug + '/members/' + userId)
      reload()
      toast(t('msg_member_removed'))
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="ws-members">
      <ul className="rows">
        {members.map((m) => (
          <li className="row" key={m.user_id}>
            <span className="row-name">{m.display_name || m.email}</span>
            <span className="member-role">{t(m.role)}</span>
            {m.role !== 'owner' && (
              <button
                className="btn btn-sm btn-danger"
                type="button"
                onClick={() => onRemove(m.user_id)}
              >
                {t('remove')}
              </button>
            )}
          </li>
        ))}
      </ul>
      <form className="member-add" onSubmit={onAdd}>
        <input
          className="field"
          type="email"
          placeholder={t('member_email_ph')}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <button className="btn" type="submit">
          {t('add_member')}
        </button>
      </form>
    </div>
  )
}
