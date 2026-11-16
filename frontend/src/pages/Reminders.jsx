import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useOutletContext, useSearchParams } from 'react-router'
import { api, isAbort } from '../api.js'
import { useAuth } from '../auth.jsx'
import { useI18n } from '../i18n.jsx'
import { pagePath } from '../routes.js'
import { reminderDate, localDateTime } from '../reminderDates.js'
import { useDocumentTitle } from '../useDocumentTitle.js'
import { useToast } from '../components/Toast.jsx'
import { ListSkeleton } from '../components/Skeleton.jsx'
import Markdown from '../components/Markdown.jsx'

export default function Reminders() {
  const { ws } = useOutletContext()
  return <WorkspaceReminders key={ws} ws={ws} />
}

function WorkspaceReminders({ ws }) {
  const { user } = useAuth()
  const { t, lang } = useI18n()
  const [search, setSearch] = useSearchParams()
  const [workspace, setWorkspace] = useState(ws)
  const [status, setStatus] = useState('pending')
  const [period, setPeriod] = useState('all')
  const [scope, setScope] = useState('mine')
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(null)
  const [loadingMore, setLoadingMore] = useState(false)
  const [editing, setEditing] = useState(search.has('new') ? 'new' : null)
  const request = useRef(null)
  const toast = useToast()
  useDocumentTitle(t('reminders'), ws)

  const load = useCallback(
    (offset = 0) => {
      request.current?.abort()
      const controller = new AbortController()
      request.current = controller
      setError(null)
      setLoadingMore(Boolean(offset))
      if (!offset) setData(null)
      const query = new URLSearchParams({
        workspace,
        status,
        period,
        scope,
        offset: String(offset),
      })
      api
        .get('/api/reminders?' + query, controller.signal)
        .then((fresh) =>
          setData((previous) =>
            offset && previous ? { ...fresh, items: [...previous.items, ...fresh.items] } : fresh,
          ),
        )
        .catch((e) => {
          if (!isAbort(e)) setError(e.message)
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoadingMore(false)
        })
      return controller
    },
    [workspace, status, period, scope],
  )

  useEffect(() => {
    load()
    return () => request.current?.abort()
  }, [load])

  async function changeStatus(item, nextStatus) {
    if (busy) return
    setBusy(item.id)
    try {
      await api.put(
        '/api/reminders/' + item.id + '?workspace=' + encodeURIComponent(item.workspace),
        {
          status: nextStatus,
          expected_revision: item.revision,
        },
      )
      toast(t('reminder_saved'))
      load()
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setBusy(null)
    }
  }

  function closeForm() {
    setEditing(null)
    if (search.has('new')) setSearch({}, { replace: true })
  }

  const groups = status === 'pending' ? ['overdue', 'today', 'upcoming'] : ['closed']
  return (
    <section className="settings reminders">
      <div className="reminders-heading">
        <div>
          <h1 className="settings-h1">{t('reminders')}</h1>
          <p className="card-desc">{t('reminders_desc')}</p>
        </div>
        <button className="btn btn-primary" type="button" onClick={() => setEditing('new')}>
          {t('reminder_new')}
        </button>
      </div>
      <div className="reminders-filters">
        <label>
          {t('reminder_workspace')}
          <select
            className="field"
            value={workspace}
            onChange={(e) => setWorkspace(e.target.value)}
          >
            <option value="all">{t('reminder_all_workspaces')}</option>
            {user.workspaces.map((w) => (
              <option key={w.slug} value={w.slug}>
                {w.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t('reminder_responsible')}
          <select className="field" value={scope} onChange={(e) => setScope(e.target.value)}>
            <option value="mine">{t('reminder_mine')}</option>
            <option value="workspace">{t('reminder_everyone')}</option>
          </select>
        </label>
        <label>
          {t('reminder_status')}
          <select
            className="field"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value)
              setPeriod('all')
            }}
          >
            {['pending', 'completed', 'cancelled'].map((s) => (
              <option key={s} value={s}>
                {t('reminder_' + s)}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t('reminder_period')}
          <select
            className="field"
            disabled={status !== 'pending'}
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
          >
            {['all', 'overdue', 'today', 'upcoming'].map((p) => (
              <option key={p} value={p}>
                {t('reminder_' + p)}
              </option>
            ))}
          </select>
        </label>
      </div>
      {editing && (
        <ReminderForm
          key={typeof editing === 'object' ? editing.id : 'new'}
          item={typeof editing === 'object' ? editing : null}
          defaultWorkspace={workspace === 'all' ? ws : workspace}
          initialPage={search.get('page')}
          onClose={closeForm}
          onSaved={() => {
            closeForm()
            load()
          }}
        />
      )}
      {error ? (
        <div role="alert" className="reminder-error">
          <p>{error}</p>
          <button className="btn" type="button" onClick={() => load()}>
            {t('retry')}
          </button>
        </div>
      ) : !data ? (
        <ListSkeleton />
      ) : data.items.length === 0 ? (
        <div className="placeholder">
          <h2>{t('reminders_empty')}</h2>
          <p className="muted">{t('reminders_empty_hint')}</p>
        </div>
      ) : (
        <>
          {groups.map((group) => {
            const items = data.items.filter((item) => status !== 'pending' || item.bucket === group)
            if (!items.length) return null
            return (
              <section className="reminder-group" key={group}>
                <h2>{t('reminder_' + (group === 'closed' ? status : group))}</h2>
                <ul className="rows rows--divided">
                  {items.map((item) => (
                    <li className="row reminder-row" key={item.id}>
                      <div className="row-name">
                        <h3>{item.title}</h3>
                        <p
                          className={
                            'meta' + (item.bucket === 'overdue' ? ' reminder-overdue' : '')
                          }
                        >
                          {reminderDate(item, lang)} ·{' '}
                          {item.due_date ? t('reminder_all_day') + ' · ' : ''}
                          {item.timezone}
                        </p>
                        <p className="meta">
                          {item.workspace_name} · {item.assignee_name || t('reminder_unassigned')}
                        </p>
                        {item.notes && <ReminderNotes text={item.notes} ws={item.workspace} />}
                        <ReminderHistory item={item} />
                        {item.pages.length > 0 && (
                          <ul className="reminder-links" aria-label={t('reminder_documents')}>
                            {item.pages.map((page) => (
                              <li key={page.id}>
                                {page.deleted ? (
                                  <span className="muted">
                                    {page.title} ({t('trash')})
                                  </span>
                                ) : (
                                  <Link to={pagePath(item.workspace, page.slug)}>{page.title}</Link>
                                )}
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                      <div className="row-actions">
                        {item.status === 'pending' ? (
                          <button
                            className="btn"
                            type="button"
                            disabled={busy !== null}
                            onClick={() => changeStatus(item, 'completed')}
                          >
                            {t('reminder_complete')}
                          </button>
                        ) : (
                          <button
                            className="btn"
                            type="button"
                            disabled={busy !== null}
                            onClick={() => changeStatus(item, 'pending')}
                          >
                            {t('reminder_reopen')}
                          </button>
                        )}
                        <button
                          className="btn"
                          type="button"
                          disabled={busy !== null}
                          onClick={() => setEditing(item)}
                        >
                          {t('edit')}
                        </button>
                        {item.status === 'pending' && (
                          <button
                            className="btn"
                            type="button"
                            disabled={busy !== null}
                            onClick={() => changeStatus(item, 'cancelled')}
                          >
                            {t('reminder_cancel')}
                          </button>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            )
          })}
          {data.next_offset !== null && (
            <button
              className="btn"
              type="button"
              disabled={loadingMore}
              onClick={() => load(data.next_offset)}
            >
              {t('reminder_load_more')}
            </button>
          )}
        </>
      )}
    </section>
  )
}

function ReminderNotes({ text, ws }) {
  const { t } = useI18n()
  const ref = useRef(null)
  return (
    <details className="reminder-notes">
      <summary>{t('reminder_notes')}</summary>
      <Markdown ref={ref} text={text} ws={ws} />
    </details>
  )
}

function ReminderHistory({ item }) {
  const { t, lang } = useI18n()
  const [open, setOpen] = useState(false)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    if (!open) return
    const controller = new AbortController()
    setData(null)
    setError(null)
    api
      .get(
        '/api/reminders/' + item.id + '/history?workspace=' + encodeURIComponent(item.workspace),
        controller.signal,
      )
      .then(setData)
      .catch((e) => {
        if (!isAbort(e)) setError(e.message)
      })
    return () => controller.abort()
  }, [open, item.id, item.workspace, item.revision, attempt])
  return (
    <details className="reminder-notes" onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>{t('history')}</summary>
      {error ? (
        <div role="alert">
          <p>{error}</p>
          <button className="btn btn-sm" type="button" onClick={() => setAttempt((n) => n + 1)}>
            {t('retry')}
          </button>
        </div>
      ) : !data ? (
        <p className="muted">{t('loading')}</p>
      ) : (
        <ul className="rows">
          {data.items.map((revision) => (
            <li className="row" key={revision.revision}>
              <div className="row-name">
                <span>{revision.title}</span>
                <span className="meta">
                  {reminderDate(revision, lang)} · {t('reminder_' + revision.status)}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </details>
  )
}

function ReminderForm({ item, defaultWorkspace, initialPage, onClose, onSaved }) {
  const { user } = useAuth()
  const { t } = useI18n()
  const toast = useToast()
  const [workspace, setWorkspace] = useState(item?.workspace || defaultWorkspace)
  const [title, setTitle] = useState(item?.title || '')
  const [notes, setNotes] = useState(item?.notes || '')
  const [timezone, setTimezone] = useState(
    item?.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || 'America/Bogota',
  )
  const [allDay, setAllDay] = useState(Boolean(item?.due_date))
  const [when, setWhen] = useState(item?.due_date || localDateTime(item?.due_at, timezone))
  const [assignee, setAssignee] = useState(item?.assignee_id ? String(item.assignee_id) : '')
  const [selected, setSelected] = useState(
    item?.pages.map((p) => p.slug) || (initialPage ? [initialPage] : []),
  )
  const [options, setOptions] = useState(null)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const key = useRef(crypto.randomUUID())
  const titleRef = useRef(null)
  useEffect(() => titleRef.current?.focus(), [])
  useEffect(() => {
    const controller = new AbortController()
    setOptions(null)
    setError(null)
    Promise.all([
      api.get('/api/pages?ws=' + encodeURIComponent(workspace), controller.signal),
      api.get('/api/workspaces/' + encodeURIComponent(workspace) + '/members', controller.signal),
    ])
      .then(([pages, members]) => setOptions({ pages, members }))
      .catch((e) => {
        if (!isAbort(e)) setError(e.message)
      })
    return () => controller.abort()
  }, [workspace, attempt])

  async function submit(e) {
    e.preventDefault()
    if (saving || !options) return
    setSaving(true)
    setError(null)
    const body = {
      title,
      notes,
      timezone,
      due_date: allDay ? when : null,
      due_at: allDay ? null : when,
      page_slugs: selected,
    }
    if (assignee) body.assignee_id = Number(assignee)
    else if (item?.assignee_id) {
      const me = options.members.find((member) => member.email === user.email)
      if (me) body.assignee_id = me.user_id
    }
    if (item) body.expected_revision = item.revision
    else body.idempotency_key = key.current
    try {
      const query = '?workspace=' + encodeURIComponent(workspace)
      if (item) await api.put('/api/reminders/' + item.id + query, body)
      else await api.post('/api/reminders' + query, body)
      toast(t('reminder_saved'))
      onSaved()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const activePages = options?.pages || []
  const existingMissing =
    item?.pages.filter((p) => !activePages.some((page) => page.slug === p.slug)) || []
  return (
    <form
      className="reminder-form"
      onSubmit={submit}
      aria-label={t(item ? 'reminder_edit' : 'reminder_new')}
    >
      <h2>{t(item ? 'reminder_edit' : 'reminder_new')}</h2>
      <label className="field-label" htmlFor="reminder-title">
        {t('reminder_title')}
      </label>
      <input
        ref={titleRef}
        className="field"
        id="reminder-title"
        value={title}
        maxLength={200}
        required
        onChange={(e) => setTitle(e.target.value)}
        disabled={saving}
      />
      <div className="reminders-filters">
        <label>
          {t('reminder_workspace')}
          <select
            className="field"
            value={workspace}
            disabled={Boolean(item) || saving}
            onChange={(e) => {
              setWorkspace(e.target.value)
              setSelected([])
              setAssignee('')
            }}
          >
            {user.workspaces.map((w) => (
              <option key={w.slug} value={w.slug}>
                {w.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t('reminder_responsible')}
          <select
            className="field"
            disabled={saving || !options}
            value={assignee}
            onChange={(e) => setAssignee(e.target.value)}
          >
            <option value="">
              {item?.assignee_id === null ? t('reminder_unassigned') : t('reminder_me')}
            </option>
            {options?.members.map((member) => (
              <option key={member.user_id} value={member.user_id}>
                {member.display_name || member.email}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="reminder-checkbox">
        <input
          type="checkbox"
          checked={allDay}
          disabled={saving}
          onChange={(e) => {
            setAllDay(e.target.checked)
            setWhen(e.target.checked ? when.slice(0, 10) : when ? when + 'T09:00' : '')
          }}
        />
        {t('reminder_all_day')}
      </label>
      <div className="reminders-filters">
        <label>
          {t('reminder_when')}
          <input
            className="field"
            type={allDay ? 'date' : 'datetime-local'}
            value={when}
            onChange={(e) => setWhen(e.target.value)}
            required
            disabled={saving}
          />
        </label>
        <label>
          {t('reminder_timezone')}
          <input
            className="field"
            value={timezone}
            onChange={(e) => setTimezone(e.target.value)}
            required
            disabled={saving}
          />
        </label>
      </div>
      <label className="field-label" htmlFor="reminder-notes">
        {t('reminder_notes')}
      </label>
      <textarea
        className="field"
        id="reminder-notes"
        rows={3}
        maxLength={20000}
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        disabled={saving}
      />
      <fieldset className="reminder-documents" disabled={saving || !options}>
        <legend>{t('reminder_documents')}</legend>
        {!options ? (
          <p className="muted">{t('loading')}</p>
        ) : activePages.length === 0 ? (
          <p className="muted">{t('reminder_no_documents')}</p>
        ) : (
          activePages.map((page) => (
            <label key={page.slug} className="reminder-checkbox">
              <input
                type="checkbox"
                checked={selected.includes(page.slug)}
                onChange={(e) =>
                  setSelected((values) =>
                    e.target.checked
                      ? [...values, page.slug]
                      : values.filter((v) => v !== page.slug),
                  )
                }
              />
              {page.title}
            </label>
          ))
        )}
        {existingMissing.map((page) => (
          <label key={page.slug} className="reminder-checkbox">
            <input
              type="checkbox"
              checked={selected.includes(page.slug)}
              onChange={(e) =>
                setSelected((values) =>
                  e.target.checked ? [...values, page.slug] : values.filter((v) => v !== page.slug),
                )
              }
            />
            {page.title} ({t('trash')})
          </label>
        ))}
      </fieldset>
      {error && (
        <div role="alert" className="reminder-error">
          <p>{error}</p>
          {!options && (
            <button className="btn" type="button" onClick={() => setAttempt((v) => v + 1)}>
              {t('retry')}
            </button>
          )}
        </div>
      )}
      <div className="row-actions">
        <button className="btn btn-primary" type="submit" disabled={saving || !options}>
          {t(saving ? 'saving' : 'save')}
        </button>
        <button className="btn" type="button" onClick={onClose} disabled={saving}>
          {t('cancel')}
        </button>
      </div>
    </form>
  )
}
