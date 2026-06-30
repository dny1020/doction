import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth.jsx'
import { useI18n } from '../i18n.jsx'
import LanguageToggle from '../components/LanguageToggle.jsx'

export default function Register() {
  const { register } = useAuth()
  const { t } = useI18n()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(event) {
    event.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await register(email, password)
      navigate('/')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth">
      <div className="auth-card">
        <h1 className="auth-brand">DOCTION</h1>
        <p className="muted">{t('register_subtitle')}</p>
        {error && <div className="auth-error">{error}</div>}
        <form onSubmit={onSubmit}>
          <label className="auth-label" htmlFor="email">{t('email')}</label>
          <input
            className="auth-input"
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoFocus
          />
          <label className="auth-label" htmlFor="password">{t('password')}</label>
          <input
            className="auth-input"
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <button className="btn btn-primary auth-submit" type="submit" disabled={busy}>
            {busy ? t('loading') : t('create_account')}
          </button>
        </form>
        <p className="auth-switch">
          {t('register_switch_q')} <Link to="/login">{t('log_in')}</Link>
        </p>
        <div className="auth-lang">
          <LanguageToggle />
        </div>
      </div>
    </div>
  )
}
