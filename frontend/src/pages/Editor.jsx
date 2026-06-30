import React, { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useOutletContext, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api.js'
import { useI18n } from '../i18n.jsx'
import { renderMarkdown } from '../markdown.js'

// Editor dividido: fuente markdown a la izquierda, preview en vivo a la derecha.
// `mode` es "new" (crear) o "edit" (editar una página existente).
export default function Editor({ mode }) {
  const isEdit = mode === 'edit'
  const { t } = useI18n()
  const { slug } = useParams()
  const [searchParams] = useSearchParams()
  const parentSlug = searchParams.get('parent') || ''
  const { reloadPages } = useOutletContext()
  const navigate = useNavigate()
  const textareaRef = useRef(null)

  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [loaded, setLoaded] = useState(!isEdit) // en modo "new" no hay nada que cargar
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  // En modo edición, carga el título y el contenido actuales.
  useEffect(() => {
    if (!isEdit) return
    api
      .get('/api/pages/' + slug)
      .then((page) => {
        setTitle(page.title)
        setContent(page.content)
        setLoaded(true)
      })
      .catch((e) => {
        setError(e.message)
        setLoaded(true)
      })
  }, [isEdit, slug])

  async function onSave(event) {
    event.preventDefault()
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
      reloadPages()
      navigate('/p/' + targetSlug)
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
        try {
          const res = await fetch('/api/uploads', {
            method: 'POST',
            body: form,
            credentials: 'same-origin',
          })
          const data = await res.json()
          if (res.ok && data.url) insertAtCursor('![](' + data.url + ')')
        } catch (e) {
          // Si falla la subida, simplemente no insertamos nada.
        }
      }
    }
  }

  if (!loaded) return <div className="placeholder">{t('loading')}</div>

  return (
    <form className="editor" onSubmit={onSave}>
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
          <Link className="btn" to={isEdit ? '/p/' + slug : '/'}>
            {t('cancel')}
          </Link>
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {isEdit ? t('save') : t('create')}
          </button>
        </div>
      </div>
      {error && <p className="auth-error">{error}</p>}
      <div className="editor-split">
        <textarea
          ref={textareaRef}
          className="editor-textarea"
          placeholder={t('write_markdown')}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onPaste={onPaste}
        />
        {content ? (
          <div className="prose preview" dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }} />
        ) : (
          <div className="prose preview preview-empty">{t('preview_hint')}</div>
        )}
      </div>
    </form>
  )
}
