import { useState } from 'react'
import { api } from '../../api.js'
import { useAuth } from '../../auth.jsx'
import { useI18n } from '../../i18n.jsx'
import { useToast } from '../../components/Toast.jsx'
import { AVATAR_COLORS, autoColor, avatarLetter } from '../../avatar.js'

// Mi cuenta: perfil (nombre + color de avatar) y contraseña. Los dos formularios
// vienen tal cual de la antigua página única de ajustes.
export default function AccountSection() {
  return (
    <>
      <ProfileSection />
      <PasswordSection />
    </>
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
