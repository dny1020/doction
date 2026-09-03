import { useEffect, useRef, useState } from 'react'
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
import { pagePath, wsPath } from '../routes.js'

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

  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [loaded, setLoaded] = useState(!isEdit) // en modo "new" no hay nada que cargar
  const [busy, setBusy] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
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
        initialRef.current = { title: page.title, content: page.content }
        setLoaded(true)
      })
      .catch((e) => {
        setError(e.message)
        setLoaded(true)
      })
  }, [isEdit, slug, ws])

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
      reloadPages()
      navigate(pagePath(ws, targetSlug))
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
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
            className="prose preview"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
          />
        ) : (
          <div className="prose preview preview-empty">{t('preview_hint')}</div>
        )}
      </div>
    </form>
  )
}
