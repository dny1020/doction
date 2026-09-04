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

// Editor dividido: fuente markdown a la izquierda, preview en vivo a la derecha.
// `mode` es "new" (crear) o "edit" (editar una página existente).
export default function Editor({ mode }) {
  const isEdit = mode === 'edit'
  const { t } = useI18n()
  const { slug } = useParams()
  const [searchParams] = useSearchParams()
  const parentSlug = searchParams.get('parent') || ''
  const { ws, reloadPages } = useOutletContext()
  const navigate = useNavigate()
  const toast = useToast()
  const confirm = useConfirm()
  const textareaRef = useRef(null)
  const formRef = useRef(null)
  const previewRef = useRef(null)

  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [loaded, setLoaded] = useState(!isEdit) // en modo "new" no hay nada que cargar
  const [busy, setBusy] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  // Un guardado fallido por red caída no es lo mismo que uno rechazado por el
  // servidor: el primero se reintenta cuando vuelva, el segundo hay que leerlo.
  const [offline, setOffline] = useState(false)
  // Borrador local de una sesión anterior, ofrecido para restaurar.
  const [draft, setDraft] = useState(null)
  // El markdown que se está pintando en la vista previa: va por detrás de lo que
  // se teclea, con retardo, para no re-renderizar un documento largo en cada tecla.
  const [preview, setPreview] = useState('')
  // Solo cuenta en móvil, donde el panel partido se apila: el botón que la
  // alterna está oculto por CSS a partir de 820px.
  const [showPreview, setShowPreview] = useState(false)

  // Guard de cambios sin guardar: comparamos contra lo cargado. Refs (no estado)
  // porque el blocker y beforeunload se evalúan fuera del ciclo de render.
  const initialRef = useRef({ title: '', content: '' })
  const currentRef = useRef({ title: '', content: '' })
  currentRef.current = { title, content }
  const savedRef = useRef(false) // true tras guardar: la navegación ya no se bloquea

  function isDirty() {
    if (savedRef.current) return false
    return (
      currentRef.current.title !== initialRef.current.title ||
      currentRef.current.content !== initialRef.current.content
    )
  }

  // En modo edición, carga el título y el contenido actuales.
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

  // Una página nueva a medio escribir también deja borrador.
  useEffect(() => {
    if (isEdit) return
    const saved = readDraft(ws, null)
    if (saved && (saved.title || saved.content)) setDraft(saved)
  }, [isEdit, ws])

  // Escribir el borrador con retardo: a ritmo acotado y no en cada tecla.
  useEffect(() => {
    if (!loaded || savedRef.current || draft) return
    if (title === initialRef.current.title && content === initialRef.current.content) return
    const timer = setTimeout(() => writeDraft(ws, slug, { title, content }), 600)
    return () => clearTimeout(timer)
  }, [ws, slug, title, content, loaded, draft])

  // La vista previa también va con retardo. Sin esto, teclear en un documento
  // largo re-renderiza todo el markdown en cada pulsación y se nota.
  useEffect(() => {
    const timer = setTimeout(() => setPreview(content), 150)
    return () => clearTimeout(timer)
  }, [content])

  const previewHtml = useMemo(() => renderMarkdown(preview), [preview])

  // Editando, el título sigue al campo: renombrar una página se ve en la pestaña
  // antes de guardar.
  useDocumentTitle(title ? t('edit') + ': ' + title : t('new_page'), ws)

  // La vista previa pasa por las mismas mejoras que la de lectura: resaltado,
  // diagramas y fórmulas. Sin esto el editor y el lector enseñaban cosas distintas
  // para el mismo markdown, que es justo lo que una vista previa no debe hacer.
  useEffect(() => {
    enhanceProse(previewRef.current)
  }, [previewHtml])

  // Navegación interna con cambios sin guardar → diálogo de confirmación.
  const blocker = useBlocker(() => isDirty())
  useEffect(() => {
    if (blocker.state !== 'blocked') return
    confirm(t('unsaved_changes'), { confirmLabel: t('discard'), danger: true }).then((leave) => {
      if (leave) blocker.proceed()
      else blocker.reset()
    })
  }, [blocker, confirm, t])

  // Cerrar/recargar la pestaña con cambios sin guardar → aviso nativo del navegador.
  useEffect(() => {
    function onBeforeUnload(event) {
      if (!isDirty()) return
      event.preventDefault()
      event.returnValue = '' // requerido por Chrome para mostrar el aviso
    }
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [])

  // ⌘S / Ctrl-S guarda (el listener global de atajos ignora los campos de texto
  // a propósito, así que este vive aquí). requestSubmit pasa por la validación
  // del formulario (título requerido).
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
      // El borrador se queda: es justo cuando hace falta.
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

  // Pegar una imagen en el editor: la sube a /api/uploads e inserta ![](url).
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
          // fetch a pelo (FormData), así que el workspace hay que ponerlo a mano.
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
          className="title-input"
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
          className="editor-textarea"
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
