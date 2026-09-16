import { useEffect, useState } from 'react'
import { Link, useNavigate, useOutletContext, useParams } from 'react-router-dom'
import { api } from '../api.js'
import { useI18n } from '../i18n.jsx'
import { pagePath } from '../routes.js'
import { useDocumentTitle } from '../useDocumentTitle.js'
import { useToast } from '../components/Toast.jsx'
import { useConfirm } from '../components/ConfirmDialog.jsx'

// The CSS class colouring one line of a unified diff: additions, deletions, hunk headers
// and metadata.
function diffLineClass(line) {
  if (line.startsWith('+') && !line.startsWith('+++')) return 'diff-add'
  if (line.startsWith('-') && !line.startsWith('---')) return 'diff-del'
  if (line.startsWith('@@')) return 'diff-hunk'
  if (
    line.startsWith('diff ') ||
    line.startsWith('index ') ||
    line.startsWith('+++') ||
    line.startsWith('---')
  )
    return 'diff-meta'
  return ''
}

// A page's version history (git commits). Each version can be shown as an inline diff and
// restored, which creates a new version with that content.
export default function History() {
  const { slug } = useParams()
  const { ws, pages, reloadPages } = useOutletContext()
  const { t } = useI18n()
  const navigate = useNavigate()
  const toast = useToast()
  const confirm = useConfirm()
  const [history, setHistory] = useState(null) // null = cargando
  const [error, setError] = useState(null)

  useEffect(() => {
    setHistory(null)
    setError(null)
    api
      .get('/api/pages/' + slug + '/history')
      .then(setHistory)
      .catch((e) => setError(e.message))
  }, [slug, ws])

  // The title comes from the tree the Layout already has, falling back to the slug.
  const treePage = pages.find((p) => p.slug === slug)
  const title = treePage ? treePage.title : slug
  useDocumentTitle(t('history') + ': ' + title, ws)

  async function onRestore(sha) {
    if (!(await confirm(t('confirm_restore'), { confirmLabel: t('restore') }))) return
    try {
      await api.post('/api/pages/' + slug + '/restore/' + sha)
    } catch (e) {
      toast(e.message, 'error')
      return
    }
    reloadPages()
    navigate(pagePath(ws, slug))
  }

  return (
    <div className="page-wrap">
      <article className="page">
        <header className="page-header">
          <nav className="breadcrumbs" aria-label="Breadcrumb">
            <Link to="/">{t('home')}</Link>
            <span className="crumb-sep" aria-hidden="true">
              ›
            </span>
            <Link to={pagePath(ws, slug)}>{title}</Link>
            <span className="crumb-sep" aria-hidden="true">
              ›
            </span>
            <span className="crumb-current">{t('history')}</span>
          </nav>
          <h1>{t('history')}</h1>
          <div className="page-actions">
            <Link className="btn" to={pagePath(ws, slug)}>
              {title}
            </Link>
          </div>
        </header>

        {error && <p className="meta">{error}</p>}
        {!error && history === null && <p className="meta">{t('loading')}</p>}
        {!error && history !== null && history.length === 0 && (
          <p className="meta">{t('no_history')}</p>
        )}

        {history && history.length > 0 && (
          <ul className="rows rows--divided">
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

// One version: metadata and actions. The diff only loads when "Diff" is pressed.
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
    } catch {
      setDiff('')
    } finally {
      setLoading(false)
    }
  }

  return (
    <li className="row">
      <div className="row-name">
        <span className="row-title">{commit.message}</span>
        <div className="meta history-sub">
          <span>{commit.author}</span>
          <span className="history-sep" aria-hidden="true">
            ·
          </span>
          <time>{commit.timestamp.slice(0, 16)}</time>
          <span className="history-sep" aria-hidden="true">
            ·
          </span>
          <code>{commit.sha}</code>
        </div>
        {diff !== null && (
          <div className="diff">
            {diff.split('\n').map((line, i) => (
              <span key={i} className={'diff-line ' + diffLineClass(line)}>
                {line}
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="row-actions">
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
