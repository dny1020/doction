import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, isAbort } from '../api.js'
import { useI18n } from '../i18n.jsx'
import { wsPath } from '../routes.js'
import { reminderDate } from '../reminderDates.js'

export default function PageReminders({ ws, slug }) {
  const { t, lang } = useI18n()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setData(null)
    setError(null)
    const query = new URLSearchParams({ workspace: ws, page_slug: slug, scope: 'workspace' })
    api
      .get('/api/reminders?' + query, controller.signal)
      .then(setData)
      .catch((e) => {
        if (!isAbort(e)) setError(e.message)
      })
    return () => controller.abort()
  }, [ws, slug, attempt])
  return (
    <section className="subpages page-reminders">
      <div className="subpages-hd">
        <h2>{t('reminders')}</h2>
        <Link
          className="btn btn-sm"
          to={wsPath(ws, '/reminders') + '?new=1&page=' + encodeURIComponent(slug)}
        >
          {t('reminder_new')}
        </Link>
      </div>
      {error ? (
        <div role="alert">
          <p>{error}</p>
          <button className="btn btn-sm" type="button" onClick={() => setAttempt((v) => v + 1)}>
            {t('retry')}
          </button>
        </div>
      ) : !data ? (
        <p className="muted">{t('loading')}</p>
      ) : !data.items.length ? (
        <p className="muted">{t('reminder_page_empty')}</p>
      ) : (
        <>
          <ul className="rows rows--divided">
            {data.items.map((item) => (
              <li className="row" key={item.id}>
                <div className="row-name">
                  <Link to={wsPath(ws, '/reminders')}>{item.title}</Link>
                  <span className="meta">
                    {reminderDate(item, lang)} · {item.timezone} · {item.assignee_name}
                  </span>
                </div>
              </li>
            ))}
          </ul>
          {data.next_offset !== null && (
            <Link to={wsPath(ws, '/reminders')}>{t('reminder_load_more')}</Link>
          )}
        </>
      )}
    </section>
  )
}
