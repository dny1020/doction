import React, { useEffect, useState } from 'react'
import { Link, useNavigate, useOutletContext, useParams } from 'react-router-dom'
import { api } from '../api.js'
import { useI18n } from '../i18n.jsx'

// Clase CSS para colorear una línea de diff unificado (misma lógica que el
// frontend Jinja: añadidos, borrados, cabeceras de hunk y metadatos).
function diffLineClass(line) {
  if (line.startsWith('+') && !line.startsWith('+++')) return 'diff-add'
  if (line.startsWith('-') && !line.startsWith('---')) return 'diff-del'
  if (line.startsWith('@@')) return 'diff-hunk'
  if (line.startsWith('diff ') || line.startsWith('index ') ||
      line.startsWith('+++') || line.startsWith('---')) return 'diff-meta'
  return ''
}

// Historial de versiones de una página (commits de git). Cada versión puede
// verse como diff en línea y restaurarse (crea una versión nueva con ese contenido).
export default function History() {
  const { slug } = useParams()
  const { pages, reloadPages } = useOutletContext()
  const { t } = useI18n()
  const navigate = useNavigate()
  const [history, setHistory] = useState(null) // null = cargando
  const [error, setError] = useState(null)

  useEffect(() => {
    setHistory(null)
    setError(null)
    api
      .get('/api/pages/' + slug + '/history')
      .then(setHistory)
      .catch((e) => setError(e.message))
  }, [slug])

  // El título lo sacamos del árbol que ya tiene el Layout; si no, usamos el slug.
  const treePage = pages.find((p) => p.slug === slug)
  const title = treePage ? treePage.title : slug

  async function onRestore(sha) {
    if (!window.confirm(t('confirm_restore'))) return
    await api.post('/api/pages/' + slug + '/restore/' + sha)
    reloadPages()
    navigate('/p/' + slug)
  }

  return (
    <div className="page-wrap">
      <article className="page">
        <header className="page-header">
          <nav className="breadcrumbs" aria-label="Breadcrumb">
            <Link to="/">{t('home')}</Link>
            <span className="crumb-sep" aria-hidden="true">›</span>
            <Link to={'/p/' + slug}>{title}</Link>
            <span className="crumb-sep" aria-hidden="true">›</span>
            <span className="crumb-current">{t('history')}</span>
          </nav>
          <h1>{t('history')}</h1>
          <div className="page-actions">
            <Link className="btn" to={'/p/' + slug}>{title}</Link>
          </div>
        </header>

        {error && <p className="meta">{error}</p>}
        {!error && history === null && <p className="meta">{t('loading')}</p>}
        {!error && history !== null && history.length === 0 && (
          <p className="meta">{t('no_history')}</p>
        )}

        {history && history.length > 0 && (
          <ul className="history-list">
            {history.map((commit, index) => (
              <HistoryItem
                key={commit.sha}
                slug={slug}
                commit={commit}
                canRestore={index !== 0} // la primera es la versión actual
                onRestore={onRestore}
              />
            ))}
          </ul>
        )}
      </article>
    </div>
  )
}

// Una versión: metadatos + acciones. El diff se carga solo al pulsar "Diff".
function HistoryItem({ slug, commit, canRestore, onRestore }) {
  const { t } = useI18n()
  const [diff, setDiff] = useState(null) // null = oculto; string = visible
  const [loading, setLoading] = useState(false)

  async function toggleDiff() {
    if (diff !== null) {
      setDiff(null)
      return
    }
    setLoading(true)
    try {
      const data = await api.get('/api/pages/' + slug + '/history/' + commit.sha + '/diff')
      setDiff(data.diff || '')
    } catch (e) {
      setDiff('')
    } finally {
      setLoading(false)
    }
  }

  return (
    <li className="history-item">
      <div className="history-main">
        <span className="history-msg">{commit.message}</span>
        <div className="history-sub">
          <span className="history-author">{commit.author}</span>
          <span className="history-sep" aria-hidden="true">·</span>
          <time className="history-date">{commit.timestamp.slice(0, 16)}</time>
          <span className="history-sep" aria-hidden="true">·</span>
          <code className="history-sha">{commit.sha}</code>
        </div>
        {diff !== null && (
          <div className="diff">
            {diff.split('\n').map((line, i) => (
              <span key={i} className={'diff-line ' + diffLineClass(line)}>{line}</span>
            ))}
          </div>
        )}
      </div>
      <div className="history-actions">
        <button className="btn btn-sm" type="button" onClick={toggleDiff} disabled={loading}>
          {diff !== null ? t('close') : t('diff')}
        </button>
        {canRestore && (
          <button className="btn btn-sm" type="button" onClick={() => onRestore(commit.sha)}>
            {t('restore')}
          </button>
        )}
      </div>
    </li>
  )
}
