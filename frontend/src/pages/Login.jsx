import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { Terminal } from 'lucide-react'
import { useAuth } from '../auth.jsx'
import { useI18n } from '../i18n.jsx'
import LanguageToggle from '../components/LanguageToggle.jsx'
import ThemeToggle from '../components/ThemeToggle.jsx'

export default function Login({ mode = 'login' }) {
  const auth = useAuth()
  const isRegister = mode === 'register'
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
      await (isRegister ? auth.register : auth.login)(email, password)
      navigate('/')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth">
      <aside className="auth-sheet">
        <h1 className="auth-brand brand">
          <Terminal className="brand-icon lucide" size={24} aria-hidden="true" />
          doction
        </h1>
        <p className="auth-tagline">{t(isRegister ? 'register_subtitle' : 'login_subtitle')}</p>
        <span className="auth-stamp">self-hosted · markdown · git</span>
      </aside>
      <div className="auth-main">
        <div className="card auth-card">
          <h2>{t(isRegister ? 'create_account' : 'log_in')}</h2>
          {error && <div className="auth-error">{error}</div>}
          <form onSubmit={onSubmit}>
            <label className="field-label" htmlFor="email">
              {t('email')}
            </label>
            <input
              className="field"
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
            />
            <label className="field-label" htmlFor="password">
              {t('password')}
            </label>
            <input
              className="field"
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <button className="btn btn-primary auth-submit" type="submit" disabled={busy}>
              {busy ? t('loading') : t(isRegister ? 'create_account' : 'log_in')}
            </button>
          </form>
          <p className="auth-switch">
            {isRegister ? (
              <>
                {t('register_switch_q')} <Link to="/login">{t('log_in')}</Link>
              </>
            ) : (
              <>
                {t('login_switch_q')} <Link to="/register">{t('create_an_account')}</Link>
              </>
            )}
          </p>
          <div className="auth-lang sidebar-controls">
            <LanguageToggle />
            <ThemeToggle />
          </div>
        </div>
      </div>
    </div>
  )
}
