import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { useI18n } from '../i18n.jsx'
import { useToast } from '../components/Toast.jsx'
import { useConfirm } from '../components/ConfirmDialog.jsx'
import { AVATAR_COLORS, autoColor, avatarLetter } from '../avatar.js'
import WorkspaceSettings from '../components/WorkspaceSettings.jsx'

// Página de ajustes: perfil, contraseña, tokens de API y workspaces.
// Los avisos van por los toasts globales (antes había un flash local de la página).
export default function Settings() {
  const { t } = useI18n()

  return (
    <div className="settings">
      <h1 className="settings-h1">{t('settings')}</h1>

      <ProfileSection />
      <PasswordSection />
      <TokensSection />
      <WebhooksSection />
      <WorkspaceSettings />
    </div>
  )
}

// ── Perfil: nombre visible + color del avatar ───────────────────────────────
function ProfileSection() {
  const { user, refresh } = useAuth()
  const { t } = useI18n()
  const toast = useToast()
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
      toast(t('msg_profile'))
    } catch (e) {
      toast(e.message, 'error')
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
            <label className="settings-label" htmlFor="display_name">
              {t('name')}
            </label>
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
            <input
              type="radio"
              name="avatar_color"
              checked={color === ''}
              onChange={() => setColor('')}
            />
            <span className="swatch-dot swatch-dot--auto" title={t('auto')}>
              A
            </span>
          </label>
          {AVATAR_COLORS.map((c) => (
            <label key={c} className={'swatch' + (color === c ? ' selected' : '')}>
              <input
                type="radio"
                name="avatar_color"
                checked={color === c}
                onChange={() => setColor(c)}
              />
              <span className="swatch-dot" style={{ background: c }} />
            </label>
          ))}
        </div>

        <div className="settings-actions">
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {t('save_profile')}
          </button>
        </div>
      </form>
    </section>
  )
}

// ── Contraseña ──────────────────────────────────────────────────────────────
function PasswordSection() {
  const { t } = useI18n()
  const toast = useToast()
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
      toast(t('msg_password'))
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="settings-card">
      <h2 className="settings-card-title">{t('password')}</h2>
      <p className="settings-card-desc">{t('password_desc')}</p>
      <form className="settings-form" onSubmit={onSave}>
        <label className="settings-label" htmlFor="current_password">
          {t('current_password')}
        </label>
        <input
          className="settings-input"
          id="current_password"
          type="password"
          autoComplete="current-password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          required
        />
        <label className="settings-label" htmlFor="new_password">
          {t('new_password')}
        </label>
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
        <label className="settings-label" htmlFor="confirm_password">
          {t('repeat_new_password')}
        </label>
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
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {t('change_password')}
          </button>
        </div>
      </form>
    </section>
  )
}

// ── Webhooks de salida ──────────────────────────────────────────────────────
// Mismo trato que un PAT: el secreto se enseña una vez y no se vuelve a listar.
// El receptor lo necesita para verificar la cabecera X-Doction-Signature.
function WebhooksSection() {
  const { t } = useI18n()
  const toast = useToast()
  const confirm = useConfirm()
  const [hooks, setHooks] = useState([])
  const [url, setUrl] = useState('')
  const [events, setEvents] = useState('')
  const [newSecret, setNewSecret] = useState(null)
  const [busy, setBusy] = useState(false)

  function reload() {
    api
      .get('/api/webhooks')
      .then(setHooks)
      .catch(() => setHooks([]))
  }
  useEffect(reload, [])

  async function onCreate(event) {
    event.preventDefault()
    setBusy(true)
    try {
      const created = await api.post('/api/webhooks', { url: url.trim(), events: events.trim() })
      setNewSecret(created.secret)
      setUrl('')
      setEvents('')
      reload()
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  async function onDelete(id) {
    if (!(await confirm(t('confirm_delete_webhook'), { confirmLabel: t('delete'), danger: true })))
      return
    try {
      await api.del('/api/webhooks/' + id)
      reload()
    } catch (e) {
      toast(e.message, 'error')
    }
  }

  return (
    <section className="settings-card">
      <h2 className="settings-card-title">{t('webhooks')}</h2>
      <p className="settings-card-desc">{t('webhooks_desc')}</p>

      {newSecret && (
        <div className="token-reveal">
          <p className="token-reveal-label">{t('secret_shown_once')}</p>
          <div className="token-reveal-row">
            <code className="token-value">{newSecret}</code>
            <button
              className="btn btn-sm"
              type="button"
              onClick={() =>
                navigator.clipboard
                  .writeText(newSecret)
                  .then(() => toast(t('copied')))
                  .catch((e) => toast(e.message, 'error'))
              }
            >
              {t('copy')}
            </button>
          </div>
        </div>
      )}

      {hooks.length > 0 && (
        <ul className="token-list">
          {hooks.map((h) => (
            <li className="token-row" key={h.id}>
              <div className="token-info">
                <span className="token-name">{h.url}</span>
                <span className="token-meta">
                  {h.events || t('all_events')}
                  {h.last_status && (
                    <>
                      <span className="crumb-sep" aria-hidden="true">
                        ·
                      </span>
                      {h.last_status}
                    </>
                  )}
                </span>
              </div>
              <button
                className="btn btn-sm btn-danger"
                type="button"
                onClick={() => onDelete(h.id)}
              >
                {t('delete')}
              </button>
            </li>
          ))}
        </ul>
      )}

      <form className="token-add" onSubmit={onCreate}>
        <input
          className="settings-input"
          type="url"
          required
          placeholder={t('webhook_url_ph')}
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <input
          className="settings-input"
          type="text"
          placeholder={t('webhook_events_ph')}
          value={events}
          onChange={(e) => setEvents(e.target.value)}
        />
        <button className="btn btn-primary" type="submit" disabled={busy}>
          {t('create')}
        </button>
      </form>
    </section>
  )
}

// ── Tokens de API ───────────────────────────────────────────────────────────
function TokensSection() {
  const { t } = useI18n()
  const toast = useToast()
  const confirm = useConfirm()
  const [tokens, setTokens] = useState([])
  const [name, setName] = useState('')
  const [newToken, setNewToken] = useState(null) // texto plano, mostrado una sola vez
  const [busy, setBusy] = useState(false)

  function reload() {
    api
      .get('/api/tokens')
      .then(setTokens)
      .catch(() => setTokens([]))
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
      toast(e.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  async function onRevoke(id) {
    if (!(await confirm(t('confirm_revoke_token'), { confirmLabel: t('revoke'), danger: true })))
      return
    try {
      await api.del('/api/tokens/' + id)
      reload()
      toast(t('msg_token_revoked'))
    } catch (e) {
      toast(e.message, 'error')
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
              // El portapapeles rechaza en contextos no seguros; sin el catch, copiar
              // fallaba en silencio y el token parecía copiado.
              onClick={() =>
                navigator.clipboard
                  .writeText(newToken)
                  .then(() => toast(t('copied')))
                  .catch((e) => toast(e.message, 'error'))
              }
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
                  <span className="crumb-sep" aria-hidden="true">
                    ·
                  </span>
                  {tok.last_used_at
                    ? t('last_used') + ' ' + tok.last_used_at.slice(0, 10)
                    : t('token_never_used')}
                </span>
              </div>
              <button
                className="btn btn-sm btn-danger"
                type="button"
                onClick={() => onRevoke(tok.id)}
              >
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
        <button className="btn btn-primary" type="submit" disabled={busy}>
          {t('create_token')}
        </button>
      </form>
    </section>
  )
}
