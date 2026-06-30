import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { useI18n } from '../i18n.jsx'
import { AVATAR_COLORS, autoColor, avatarLetter } from '../avatar.js'
import WorkspaceSettings from '../components/WorkspaceSettings.jsx'

// Página de ajustes: perfil, contraseña, tokens de API y workspaces.
// El mensaje de aviso (flash) vive aquí arriba y lo comparten las secciones.
export default function Settings() {
  const { t } = useI18n()
  const [flash, setFlash] = useState(null) // { tone: 'ok' | 'error', text }

  return (
    <div className="settings">
      <h1 className="settings-h1">{t('settings')}</h1>

      {flash && <div className={'settings-flash settings-flash--' + flash.tone}>{flash.text}</div>}

      <ProfileSection setFlash={setFlash} />
      <PasswordSection setFlash={setFlash} />
      <TokensSection setFlash={setFlash} />
      <WorkspaceSettings setFlash={setFlash} />
    </div>
  )
}

// ── Perfil: nombre visible + color del avatar ───────────────────────────────
function ProfileSection({ setFlash }) {
  const { user, refresh } = useAuth()
  const { t } = useI18n()
  const [name, setName] = useState(user.display_name || '')
  const [color, setColor] = useState(user.avatar_color || '') // '' = automático
  const [busy, setBusy] = useState(false)

  const previewColor = color || autoColor(user.email)
  const previewLetter = avatarLetter(name, user.email)

  async function onSave(event) {
    event.preventDefault()
    setBusy(true)
    try {
      await api.post('/api/settings/profile', { display_name: name, avatar_color: color })
      await refresh() // refresca el avatar de la barra lateral
      setFlash({ tone: 'ok', text: t('msg_profile') })
    } catch (e) {
      setFlash({ tone: 'error', text: e.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="settings-card">
      <h2 className="settings-card-title">{t('profile')}</h2>
      <p className="settings-card-desc">{t('profile_desc')}</p>
      <form className="settings-form" onSubmit={onSave}>
        <div className="profile-row">
          <div className="profile-preview" style={{ background: previewColor }}>
            {previewLetter}
          </div>
          <div className="profile-fields">
            <label className="settings-label" htmlFor="display_name">{t('name')}</label>
            <input
              className="settings-input"
              id="display_name"
              type="text"
              maxLength={40}
              value={name}
              placeholder={user.email}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
        </div>

        <label className="settings-label">{t('avatar_color')}</label>
        <div className="color-swatches">
          <label className={'swatch swatch--auto' + (color === '' ? ' selected' : '')}>
            <input type="radio" name="avatar_color" checked={color === ''} onChange={() => setColor('')} />
            <span className="swatch-dot swatch-dot--auto" title={t('auto')}>A</span>
          </label>
          {AVATAR_COLORS.map((c) => (
            <label key={c} className={'swatch' + (color === c ? ' selected' : '')}>
              <input type="radio" name="avatar_color" checked={color === c} onChange={() => setColor(c)} />
              <span className="swatch-dot" style={{ background: c }} />
            </label>
          ))}
        </div>

        <div className="settings-actions">
          <button className="btn btn-primary" type="submit" disabled={busy}>{t('save_profile')}</button>
        </div>
      </form>
    </section>
  )
}

// ── Contraseña ──────────────────────────────────────────────────────────────
function PasswordSection({ setFlash }) {
  const { t } = useI18n()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSave(event) {
    event.preventDefault()
    setBusy(true)
    try {
      await api.post('/api/settings/password', {
        current_password: current,
        new_password: next,
        confirm_password: confirm,
      })
      setCurrent('')
      setNext('')
      setConfirm('')
      setFlash({ tone: 'ok', text: t('msg_password') })
    } catch (e) {
      setFlash({ tone: 'error', text: e.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="settings-card">
      <h2 className="settings-card-title">{t('password')}</h2>
      <p className="settings-card-desc">{t('password_desc')}</p>
      <form className="settings-form" onSubmit={onSave}>
        <label className="settings-label" htmlFor="current_password">{t('current_password')}</label>
        <input
          className="settings-input"
          id="current_password"
          type="password"
          autoComplete="current-password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          required
        />
        <label className="settings-label" htmlFor="new_password">{t('new_password')}</label>
        <input
          className="settings-input"
          id="new_password"
          type="password"
          autoComplete="new-password"
          minLength={8}
          value={next}
          onChange={(e) => setNext(e.target.value)}
          required
        />
        <label className="settings-label" htmlFor="confirm_password">{t('repeat_new_password')}</label>
        <input
          className="settings-input"
          id="confirm_password"
          type="password"
          autoComplete="new-password"
          minLength={8}
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
        />
        <div className="settings-actions">
          <button className="btn btn-primary" type="submit" disabled={busy}>{t('change_password')}</button>
        </div>
      </form>
    </section>
  )
}

// ── Tokens de API ───────────────────────────────────────────────────────────
function TokensSection({ setFlash }) {
  const { t } = useI18n()
  const [tokens, setTokens] = useState([])
  const [name, setName] = useState('')
  const [newToken, setNewToken] = useState(null) // texto plano, mostrado una sola vez
  const [busy, setBusy] = useState(false)

  function reload() {
    api.get('/api/tokens').then(setTokens).catch(() => setTokens([]))
  }
  useEffect(reload, [])

  async function onCreate(event) {
    event.preventDefault()
    setBusy(true)
    try {
      const created = await api.post('/api/tokens', { name: name.trim() || 'token' })
      setNewToken(created.token)
      setName('')
      reload()
    } catch (e) {
      setFlash({ tone: 'error', text: e.message })
    } finally {
      setBusy(false)
    }
  }

  async function onRevoke(id) {
    if (!window.confirm(t('confirm_revoke_token'))) return
    try {
      await api.del('/api/tokens/' + id)
      reload()
      setFlash({ tone: 'ok', text: t('msg_token_revoked') })
    } catch (e) {
      setFlash({ tone: 'error', text: e.message })
    }
  }

  return (
    <section className="settings-card">
      <h2 className="settings-card-title">{t('api_tokens')}</h2>
      <p className="settings-card-desc">{t('api_tokens_desc')}</p>

      {newToken && (
        <div className="token-reveal">
          <p className="token-reveal-label">{t('token_shown_once')}</p>
          <div className="token-reveal-row">
            <code className="token-value">{newToken}</code>
            <button
              className="btn btn-sm"
              type="button"
              onClick={() => navigator.clipboard.writeText(newToken)}
            >
              {t('copy')}
            </button>
          </div>
        </div>
      )}

      {tokens.length > 0 && (
        <ul className="token-list">
          {tokens.map((tok) => (
            <li className="token-row" key={tok.id}>
              <div className="token-info">
                <span className="token-name">{tok.name}</span>
                <span className="token-meta">
                  {t('created')} {tok.created_at.slice(0, 10)}
                  <span className="crumb-sep" aria-hidden="true">·</span>
                  {tok.last_used_at ? t('last_used') + ' ' + tok.last_used_at.slice(0, 10) : t('token_never_used')}
                </span>
              </div>
              <button className="btn btn-sm btn-danger" type="button" onClick={() => onRevoke(tok.id)}>
                {t('revoke')}
              </button>
            </li>
          ))}
        </ul>
      )}

      <form className="token-add" onSubmit={onCreate}>
        <input
          className="settings-input"
          type="text"
          maxLength={60}
          placeholder={t('token_name_ph')}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <button className="btn btn-primary" type="submit" disabled={busy}>{t('create_token')}</button>
      </form>
    </section>
  )
}
