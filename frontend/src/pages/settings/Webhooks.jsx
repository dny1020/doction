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
  const [deleting, setDeleting] = useState(null)

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
    if (deleting) return
    if (!(await confirm(t('confirm_delete_webhook'), { confirmLabel: t('delete'), danger: true })))
      return
    setDeleting(id)
    try {
      await api.del('/api/webhooks/' + id)
      reload()
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setDeleting(null)
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
            <WebhookRow
              key={h.id}
              hook={h}
              onDelete={() => onDelete(h.id)}
              busy={deleting === h.id}
            />
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

// Una fila de la lista: el estado a la vista y el historial al abrirla.
//
// doction entrega hacia fuera —firma el evento y lo manda, reintentando con
// backoff—, así que lo que hace falta saber es si esas entregas están llegando.
// `last_status` solo cuenta el último intento; una cola atascada detrás no se veía.
function WebhookRow({ hook, onDelete, busy }) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const [deliveries, setDeliveries] = useState(null) // null = sin cargar
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!open) return
    setFailed(false)
    api
      .get('/api/webhooks/' + hook.id + '/deliveries')
      .then(setDeliveries)
      .catch(() => setFailed(true))
  }, [open, hook.id])

  let health = t('hook_never_fired')
  if (hook.failed > 0) health = t('hook_failing')
  else if (hook.pending > 0) health = t('hook_pending')
  else if (hook.last_status) health = t('hook_delivering')

  return (
    <li className="token-row token-row--stacked">
      <div className="token-row-head">
        <div className="token-info">
          <span className="token-name">{hook.url}</span>
          <span className="token-meta">
            {hook.events || t('all_events')}
            <span className="crumb-sep" aria-hidden="true">
              ·
            </span>
            <span className={'hook-health hook-health--' + (hook.failed > 0 ? 'bad' : 'ok')}>
              {health}
            </span>
          </span>
        </div>
        <div className="token-row-actions">
          <button
            className="btn btn-sm"
            type="button"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            {t('deliveries')}
          </button>
          <button
            className="btn btn-sm btn-danger"
            type="button"
            onClick={onDelete}
            disabled={busy}
          >
            {t('delete')}
          </button>
        </div>
      </div>

      {open && (
        <div className="delivery-list">
          {failed ? (
            <p className="muted">{t('deliveries_unavailable')}</p>
          ) : deliveries === null ? (
            <p className="muted">{t('loading')}</p>
          ) : deliveries.length === 0 ? (
            <p className="muted">{t('hook_never_fired')}</p>
          ) : (
            <ul>
              {deliveries.map((d) => (
                <li key={d.id} className={'delivery delivery--' + d.status}>
                  <span className="delivery-event">{d.event}</span>
                  <span className="delivery-when">
                    {(d.delivered_at || d.next_attempt_at || '').replace('T', ' ').slice(0, 16)}
                  </span>
                  <span className="delivery-status">
                    {t('delivery_' + d.status)}
                    {d.attempts > 1 && ' · ' + d.attempts + '×'}
                  </span>
                  {d.last_error && <span className="delivery-error">{d.last_error}</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </li>
  )
}
