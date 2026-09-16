import { useEffect, useState } from 'react'
import { api } from '../../api.js'
import { useI18n } from '../../i18n.jsx'
import { useToast } from '../../components/Toast.jsx'
import { useConfirm } from '../../components/ConfirmDialog.jsx'

// ── Tokens de API ───────────────────────────────────────────────────────────
export default function TokensSection() {
  const { t } = useI18n()
  const toast = useToast()
  const confirm = useConfirm()
  const [tokens, setTokens] = useState([])
  const [name, setName] = useState('')
  const [newToken, setNewToken] = useState(null) // texto plano, mostrado una sola vez
  const [busy, setBusy] = useState(false)
  const [revoking, setRevoking] = useState(null)

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
    if (revoking) return
    if (!(await confirm(t('confirm_revoke_token'), { confirmLabel: t('revoke'), danger: true })))
      return
    setRevoking(id)
    try {
      await api.del('/api/tokens/' + id)
      reload()
      toast(t('msg_token_revoked'))
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setRevoking(null)
    }
  }

  return (
    <section className="card">
      <h2 className="card-title">{t('api_tokens')}</h2>
      <p className="card-desc">{t('api_tokens_desc')}</p>

      {newToken && (
        <div className="secret-reveal">
          <p className="secret-note">{t('token_shown_once')}</p>
          <div className="secret-row">
            <code className="secret-value">{newToken}</code>
            <button
              className="btn btn-sm"
              type="button"
              // The clipboard rejects in insecure contexts; without the catch, copying
              // failed silently and the token looked copied.
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
        <ul className="rows rows--divided">
          {tokens.map((tok) => (
            <li className="row" key={tok.id}>
              <div className="row-name">
                <span className="row-title">{tok.name}</span>
                <span className="meta">
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
                disabled={revoking === tok.id}
              >
                {t('revoke')}
              </button>
            </li>
          ))}
        </ul>
      )}

      <form className="add-form" onSubmit={onCreate}>
        <input
          className="field"
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
