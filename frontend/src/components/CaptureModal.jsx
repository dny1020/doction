import { useEffect, useRef, useState } from 'react'
import { useI18n } from '../i18n.jsx'
import { useToast } from './Toast.jsx'
import { api } from '../api.js'

// Quick capture (⌘/Ctrl + Shift + K): saved as `type: memo`, so it lands in the inbox
// feed, not the tree. Reuses the `.palette*` classes, like CommandPalette.
export default function CaptureModal({ onCaptured }) {
  const { t } = useI18n()
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [saving, setSaving] = useState(false)
  const inputRef = useRef(null)
  const prevFocusRef = useRef(null)

  // ⌘K is already the command palette, so capture uses ⌘⇧K.
  useEffect(() => {
    function onKey(event) {
      if ((event.metaKey || event.ctrlKey) && event.shiftKey && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setOpen((isOpen) => !isOpen)
      } else if (event.key === 'Escape') {
        setOpen(false)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    if (open) {
      prevFocusRef.current = document.activeElement
      setText('')
      inputRef.current?.focus()
    } else if (prevFocusRef.current) {
      prevFocusRef.current.focus?.()
      prevFocusRef.current = null
    }
  }, [open])

  async function save() {
    const body = text.trim()
    if (!body || saving) return
    setSaving(true)
    try {
      // No title: the backend derives one from the first line and gives it a
      // timestamped slug, so a hundred captures do not collide.
      await api.post('/api/pages', { content: '---\ntype: memo\n---\n\n' + body })
      setOpen(false)
      toast(t('capture_saved'))
      onCaptured?.()
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  function onInputKey(event) {
    if (event.key === 'Escape') {
      setOpen(false)
    } else if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault()
      save()
    }
  }

  return (
    <div
      className={'palette' + (open ? ' open' : '')}
      aria-hidden={open ? 'false' : 'true'}
      {...(open ? {} : { inert: '' })}
      onClick={(event) => {
        if (event.target === event.currentTarget) setOpen(false)
      }}
    >
      <div className="palette-box" role="dialog" aria-modal="true" aria-label={t('capture')}>
        <textarea
          ref={inputRef}
          className="palette-input capture-input"
          rows={5}
          placeholder={t('capture_placeholder')}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onInputKey}
        />
        <div className="capture-actions">
          <span className="muted">{t('capture_hint')}</span>
          <button
            className="btn btn-primary btn-sm"
            type="button"
            onClick={save}
            disabled={saving || !text.trim()}
          >
            {t('save')}
          </button>
        </div>
      </div>
    </div>
  )
}
