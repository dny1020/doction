import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth.jsx'
import { useI18n } from '../i18n.jsx'
import LanguageToggle from '../components/LanguageToggle.jsx'

export default function Login() {
  const { login } = useAuth()
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
      await login(email, password)
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
        <p className="muted">{t('login_subtitle')}</p>
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
            {busy ? t('loading') : t('log_in')}
          </button>
        </form>
        <p className="auth-switch">
          {t('login_switch_q')} <Link to="/register">{t('create_an_account')}</Link>
        </p>
        <div className="auth-lang">
          <LanguageToggle />
        </div>
      </div>
    </div>
  )
}
