import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Link,
  useBlocker,
  useNavigate,
  useOutletContext,
  useParams,
  useSearchParams,
} from 'react-router-dom'
import { api, withWorkspace } from '../api.js'
import { useI18n } from '../i18n.jsx'
import { useToast } from '../components/Toast.jsx'
import { useConfirm } from '../components/ConfirmDialog.jsx'
import { renderMarkdown } from '../markdown.js'
import { enhanceProse } from '../prose.js'
import { pagePath, wsPath } from '../routes.js'
import { clearDraft, readDraft, writeDraft } from '../drafts.js'
import { useDocumentTitle } from '../useDocumentTitle.js'

// Split editor: markdown source left, live preview right. `mode` is "new" or "edit".
export default function Editor({ mode }) {
  const isEdit = mode === 'edit'
  const { t } = useI18n()
  const { slug } = useParams()
  const [searchParams] = useSearchParams()
  const parentSlug = searchParams.get('parent') || ''
  // A wikilink to a page that does not exist arrives with its target as the title.
  const seededTitle = searchParams.get('title') || ''
  const { ws, pages, reloadPages } = useOutletContext()
  const navigate = useNavigate()
  const toast = useToast()
  const confirm = useConfirm()
  const textareaRef = useRef(null)
  const formRef = useRef(null)
  const previewRef = useRef(null)

  const slugSet = useMemo(() => new Set(pages.map((p) => p.slug)), [pages])
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [loaded, setLoaded] = useState(!isEdit) // nothing to load in "new" mode
  const [busy, setBusy] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  // A save that failed on a dead network is not one the server rejected: the first is
  // retried when it returns, the second has to be read.
  const [offline, setOffline] = useState(false)
  // A local draft from an earlier session, offered for restore.
  const [draft, setDraft] = useState(null)
  // The markdown the preview is painting: debounced behind what is typed, so a long
  // document is not re-rendered on every keystroke.
  const [preview, setPreview] = useState('')
  // Only matters on mobile, where the split stacks; the toggle is hidden above 820px.
  const [showPreview, setShowPreview] = useState(false)

  // Unsaved-changes guard, compared against what was loaded. Refs and not state, because
  // the blocker and beforeunload are evaluated outside the render cycle.
  const initialRef = useRef({ title: '', content: '' })
  const currentRef = useRef({ title: '', content: '' })
  currentRef.current = { title, content }
  const savedRef = useRef(false) // true after a save, so navigation stops being blocked

  function isDirty() {
    if (savedRef.current) return false
    return (
      currentRef.current.title !== initialRef.current.title ||
      currentRef.current.content !== initialRef.current.content
    )
  }

  // In edit mode, load the current title and content.
  useEffect(() => {
    if (!isEdit) return
    api
      .get('/api/pages/' + slug)
      .then((page) => {
        setTitle(page.title)
        setContent(page.content)
        setPreview(page.content)
        initialRef.current = { title: page.title, content: page.content }
        const saved = readDraft(ws, slug)
        if (saved && (saved.title !== page.title || saved.content !== page.content)) {
          setDraft(saved)
        }
        setLoaded(true)
      })
      .catch((e) => {
        setError(e.message)
        setLoaded(true)
      })
  }, [isEdit, slug, ws])

  // A half-written new page leaves a draft too.
  useEffect(() => {
    if (isEdit) return
    const saved = readDraft(ws, null)
    if (saved && (saved.title || saved.content)) setDraft(saved)
  }, [isEdit, ws])

  // A broken wikilink prefills the title (never over a draft) and moves the unsaved
  // baseline, so leaving untouched does not ask to discard changes.
  useEffect(() => {
    if (isEdit || !seededTitle) return
    setTitle((current) => {
      if (current) return current
      initialRef.current = { ...initialRef.current, title: seededTitle }
      return seededTitle
    })
  }, [isEdit, seededTitle])

  // Write the draft on a debounce, not on every keystroke.
  useEffect(() => {
    if (!loaded || savedRef.current || draft) return
    if (title === initialRef.current.title && content === initialRef.current.content) return
    const timer = setTimeout(() => writeDraft(ws, slug, { title, content }), 600)
    return () => clearTimeout(timer)
  }, [ws, slug, title, content, loaded, draft])

  // The preview is debounced too: without it, typing in a long document re-renders all
  // of the markdown on every keypress and it shows.
  useEffect(() => {
    const timer = setTimeout(() => setPreview(content), 150)
    return () => clearTimeout(timer)
  }, [content])

  const previewHtml = useMemo(
    () => renderMarkdown(preview, { ws, slugs: slugSet }),
    [preview, ws, slugSet],
  )

  // While editing, the document title follows the field, so a rename shows in the tab
  // before it is saved.
  useDocumentTitle(title ? t('edit') + ': ' + title : t('new_page'), ws)

  // The preview runs the same enhancements as the reading view, so the editor and the
  // reader never show two different things for one document.
  useEffect(() => {
    enhanceProse(previewRef.current)
  }, [previewHtml])

  // In-app navigation with unsaved changes asks for confirmation.
  const blocker = useBlocker(() => isDirty())
  useEffect(() => {
    if (blocker.state !== 'blocked') return
    confirm(t('unsaved_changes'), { confirmLabel: t('discard'), danger: true }).then((leave) => {
      if (leave) blocker.proceed()
      else blocker.reset()
    })
  }, [blocker, confirm, t])

  // Closing or reloading the tab with unsaved changes gets the browser's own prompt.
  useEffect(() => {
    function onBeforeUnload(event) {
      if (!isDirty()) return
      event.preventDefault()
      event.returnValue = '' // Chrome needs it to show the prompt
    }
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [])

  // ⌘S / Ctrl-S saves. The global shortcut listener ignores text fields on purpose, so
  // this one lives here; requestSubmit goes through the form's validation.
  useEffect(() => {
    function onKey(event) {
      if ((event.metaKey || event.ctrlKey) && (event.key === 's' || event.key === 'S')) {
        event.preventDefault()
        formRef.current?.requestSubmit()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  async function onSave(event) {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      let targetSlug = slug
      if (isEdit) {
        await api.put('/api/pages/' + slug, { title, content })
      } else {
        const body = { title, content }
        if (parentSlug) body.parent_slug = parentSlug
        const created = await api.post('/api/pages', body)
        targetSlug = created.slug
      }
      savedRef.current = true
      clearDraft(ws, isEdit ? slug : null)
      setOffline(false)
      reloadPages()
      navigate(pagePath(ws, targetSlug))
    } catch (e) {
      // The draft stays: this is exactly when it is needed.
      setOffline(Boolean(e.offline))
      setError(e.status === 401 ? t('session_expired') : e.offline ? t('offline_desc') : e.message)
      setBusy(false)
    }
  }

  function restoreDraft() {
    setTitle(draft.title)
    setContent(draft.content)
    setDraft(null)
  }

  function discardDraft() {
    clearDraft(ws, isEdit ? slug : null)
    setDraft(null)
  }

  function insertAtCursor(text) {
    const el = textareaRef.current
    if (!el) {
      setContent(content + text)
      return
    }
    const next = content.slice(0, el.selectionStart) + text + content.slice(el.selectionEnd)
    setContent(next)
  }

  // Pasting an image uploads it to /api/uploads and inserts ![](url).
  async function onPaste(event) {
    const items = event.clipboardData ? Array.from(event.clipboardData.items) : []
    for (const item of items) {
      if (item.type && item.type.indexOf('image/') === 0) {
        event.preventDefault()
        const file = item.getAsFile()
        if (!file) continue
        const form = new FormData()
        form.append('file', file, file.name || 'pasted.png')
        setUploading(true)
        try {
          // A bare fetch with FormData, so the workspace has to be added by hand.
          const res = await fetch(withWorkspace('/api/uploads'), {
            method: 'POST',
            body: form,
            credentials: 'same-origin',
          })
          let data = null
          try {
            data = await res.json()
          } catch {
            data = null
          }
          if (res.ok && data && data.url) {
            insertAtCursor('![](' + data.url + ')')
            toast(t('img_uploaded'))
          } else {
            toast((data && data.detail) || t('img_upload_failed'), 'error')
          }
        } catch {
          toast(t('img_upload_failed'), 'error')
        } finally {
          setUploading(false)
        }
      }
    }
  }

  if (!loaded) return <div className="placeholder">{t('loading')}</div>

  return (
    <form className="editor" onSubmit={onSave} ref={formRef}>
      <div className="editor-bar">
        <input
          className="field field--bare title-input"
          type="text"
          placeholder={t('title')}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
          autoFocus
        />
        <div className="editor-actions">
          {uploading && <span className="meta">{t('img_uploading')}</span>}
          <button
            className="btn editor-preview-toggle"
            type="button"
            onClick={() => setShowPreview((v) => !v)}
          >
            {showPreview ? t('write') : t('preview')}
          </button>
          <Link className="btn" to={isEdit ? pagePath(ws, slug) : wsPath(ws)}>
            {t('cancel')}
          </Link>
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {isEdit ? t('save') : t('create')}
          </button>
        </div>
      </div>
      {draft && (
        <div className="editor-notice">
          <span>{t('draft_found')}</span>
          <span className="editor-notice-actions">
            <button className="btn btn-sm btn-primary" type="button" onClick={restoreDraft}>
              {t('draft_restore')}
            </button>
            <button className="btn btn-sm" type="button" onClick={discardDraft}>
              {t('draft_discard')}
            </button>
          </span>
        </div>
      )}
      {offline && (
        <div className="editor-notice editor-notice--warn">
          <span>{t('offline_title')}</span>
          <span className="editor-notice-actions">
            <button
              className="btn btn-sm"
              type="button"
              onClick={() => formRef.current?.requestSubmit()}
            >
              {t('retry')}
            </button>
          </span>
        </div>
      )}
      {error && <p className="auth-error">{error}</p>}
      <div className={'editor-split' + (showPreview ? ' editor-split--preview' : '')}>
        <textarea
          ref={textareaRef}
          className="field field--bare editor-textarea"
          placeholder={t('write_markdown')}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onPaste={onPaste}
        />
        {content ? (
          <div
            ref={previewRef}
            className="prose preview"
            dangerouslySetInnerHTML={{ __html: previewHtml }}
          />
        ) : (
          <div className="prose preview preview-empty">{t('preview_hint')}</div>
        )}
      </div>
    </form>
  )
}
