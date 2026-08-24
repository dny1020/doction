import { useEffect, useState } from 'react'
import { api } from '../../api.js'
import { useI18n } from '../../i18n.jsx'
import { useToast } from '../../components/Toast.jsx'
import { useConfirm } from '../../components/ConfirmDialog.jsx'

export default function WebhooksSection() {
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
