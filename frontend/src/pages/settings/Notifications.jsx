import { useCallback, useEffect, useState } from 'react'
import { api, isAbort } from '../../api.js'
import { useI18n } from '../../i18n.jsx'
import { useToast } from '../../components/Toast.jsx'
import { ListSkeleton } from '../../components/Skeleton.jsx'

export default function NotificationPreferences() {
  const { t } = useI18n()
  const toast = useToast()
  const [settings, setSettings] = useState(null)
  const [token, setToken] = useState('')
  const [clearToken, setClearToken] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [attempt, setAttempt] = useState(0)
  const [dirty, setDirty] = useState(false)
  const load = useCallback((signal) => {
    setError(null)
    api
      .get('/api/notification-settings', signal)
      .then((value) => {
        setSettings(value)
        setDirty(false)
      })
      .catch((e) => {
        if (!isAbort(e)) setError(e.message)
      })
  }, [])
  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal)
    return () => controller.abort()
  }, [load, attempt])

  function change(field, value) {
    setSettings((previous) => ({ ...previous, [field]: value }))
    setDirty(true)
  }

  async function save(e) {
    e.preventDefault()
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      const body = {
        enabled: settings.enabled,
        ntfy_url: settings.ntfy_url,
        date_only_time: settings.date_only_time,
      }
      if (clearToken || token) body.token = clearToken ? '' : token
      const result = await api.put('/api/notification-settings', body)
      setSettings(result)
      setToken('')
      setClearToken(false)
      setDirty(false)
      toast(t('notif_saved'))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function test() {
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      await api.post('/api/notification-settings/test')
      toast(t('notif_test_sent'))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card">
      <h2 className="card-title">{t('notif_title')}</h2>
      <p className="card-desc">{t('notif_description')}</p>
      {error && (
        <div role="alert">
          <p>{error}</p>
          {!settings && (
            <button className="btn" type="button" onClick={() => setAttempt((value) => value + 1)}>
              {t('retry')}
            </button>
          )}
        </div>
      )}
      {!settings ? (
        !error && <ListSkeleton rows={3} />
      ) : (
        <form className="settings-form" onSubmit={save}>
          <label className="reminder-checkbox">
            <input
              type="checkbox"
              checked={settings.enabled}
              disabled={busy}
              onChange={(e) => change('enabled', e.target.checked)}
            />
            {t('notif_enable')}
          </label>
          <label className="field-label" htmlFor="ntfy-url">
            {t('notif_url')}
          </label>
          <input
            className="field"
            id="ntfy-url"
            type="url"
            value={settings.ntfy_url}
            required={settings.enabled}
            disabled={busy}
            onChange={(e) => change('ntfy_url', e.target.value)}
            aria-describedby="ntfy-destination-help"
          />
          <p className="card-desc" id="ntfy-destination-help">
            {t('notif_destination_help')}
          </p>
          <label className="field-label" htmlFor="ntfy-token">
            {t('notif_token')}
          </label>
          <input
            className="field"
            id="ntfy-token"
            type="password"
            autoComplete="new-password"
            value={token}
            disabled={busy || clearToken}
            onChange={(e) => {
              setToken(e.target.value)
              setDirty(true)
            }}
            aria-describedby="ntfy-token-help"
          />
          <p className="card-desc" id="ntfy-token-help">
            {t(settings.has_token ? 'notif_token_kept' : 'notif_token_optional')}
          </p>
          {settings.has_token && (
            <label className="reminder-checkbox">
              <input
                type="checkbox"
                checked={clearToken}
                disabled={busy}
                onChange={(e) => {
                  setClearToken(e.target.checked)
                  setDirty(true)
                }}
              />
              {t('notif_clear_token')}
            </label>
          )}
          <label className="field-label" htmlFor="ntfy-clock">
            {t('notif_date_clock')}
          </label>
          <input
            className="field"
            id="ntfy-clock"
            type="time"
            required
            value={settings.date_only_time}
            disabled={busy}
            onChange={(e) => change('date_only_time', e.target.value)}
          />
          <p className="card-desc">{t('notif_clock_help')}</p>
          <p className="card-desc">{t('notif_catchup_help')}</p>
          <div className="row-actions">
            <button className="btn btn-primary" type="submit" disabled={busy}>
              {t('save')}
            </button>
            <button
              className="btn"
              type="button"
              disabled={busy || dirty || !settings.ntfy_url}
              onClick={test}
            >
              {t('notif_test')}
            </button>
          </div>
          {dirty && <p className="muted">{t('notif_save_before_test')}</p>}
        </form>
      )}
    </section>
  )
}
