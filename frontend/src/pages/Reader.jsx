import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, Navigate, useNavigate, useOutletContext, useParams } from 'react-router-dom'
import { api } from '../api.js'
import { useI18n } from '../i18n.jsx'
import { newPagePath, pagePath, wsPath } from '../routes.js'
import { useToast } from '../components/Toast.jsx'
import { useConfirm } from '../components/ConfirmDialog.jsx'
import Markdown from '../components/Markdown.jsx'
import Toc from '../components/Toc.jsx'

// Vista de lectura de una página. Pide /api/pages/{slug}/view, que trae el
// contenido + migas + subpáginas + backlinks + relacionadas en una sola llamada.
export default function Reader() {
  const { slug } = useParams()
  const { ws, pages, pagesReady, pagesError, reloadPages } = useOutletContext()
  const { t } = useI18n()
  const navigate = useNavigate()
  const toast = useToast()
  const confirm = useConfirm()
  const [view, setView] = useState(null)
  const [error, setError] = useState(null) // Error de api.js (trae .status)
  const wrapRef = useRef(null)
  const proseRef = useRef(null)

  const load = useCallback(() => {
    if (!slug || !ws) return
    setView(null)
    setError(null)
    api
      .get('/api/pages/' + slug + '/view')
      .then(setView)
      .catch(setError)
    // `ws` cuenta: el mismo slug en otro workspace es otra página.
  }, [slug, ws])

  useEffect(load, [load])

  // Ruta home (/): si hay páginas, abre la primera; si no, estado vacío — salvo
  // que el árbol no cargara (red caída ≠ workspace vacío).
  if (!slug) {
    // Sin el árbol de ESTE workspace no se decide nada: redirigir con el del
    // anterior manda a una página que aquí no existe.
    if (!pagesReady && !pagesError) return <div className="placeholder">{t('loading')}</div>
    if (pages && pages.length > 0) return <Navigate to={pagePath(ws, pages[0].slug)} replace />
    if (pagesError) {
      return (
        <div className="placeholder placeholder--error">
          <h1>{t('tree_error')}</h1>
          <button className="btn btn-primary" type="button" onClick={reloadPages}>
            {t('retry')}
          </button>
        </div>
      )
    }
    return (
      <div className="placeholder">
        <h1>{t('empty_title')}</h1>
        <Link className="btn btn-primary" to={newPagePath(ws)}>
          {t('create_this_page')}
        </Link>
      </div>
    )
  }

  if (error && error.status === 404) {
    return (
      <div className="placeholder">
        <h1>{t('nf_title')}</h1>
        <p className="muted">
          {t('nf_desc')} <code>/{slug}</code>
        </p>
        <Link className="btn btn-primary" to={wsPath(ws)}>
          {t('back_home')}
        </Link>
      </div>
    )
  }
  if (error) {
    return (
      <div className="placeholder placeholder--error">
        <h1>{t('error_title')}</h1>
        <p className="muted">{error.message}</p>
        <button className="btn btn-primary" type="button" onClick={load}>
          {t('retry')}
        </button>
      </div>
    )
  }
  if (!view) return <div className="placeholder">{t('loading')}</div>

  async function onDelete() {
    const message = t('confirm_delete_page') + ' “' + view.title + '”?'
    if (!(await confirm(message, { confirmLabel: t('delete'), danger: true }))) return
    try {
      await api.del('/api/pages/' + slug)
    } catch (e) {
      toast(e.message, 'error')
      return
    }
    reloadPages()
    navigate(wsPath(ws))
  }

  const updatedDate = view.updated_at ? view.updated_at.slice(0, 10) : ''
  const editor = view.updated_by_name || view.updated_by_email

  return (
    <div className="page-wrap" ref={wrapRef}>
      <article className="page">
        <header className="page-header">
          <nav className="breadcrumbs" aria-label="Breadcrumb">
            <Link to={wsPath(ws)}>{t('home')}</Link>
            {view.breadcrumbs.map((crumb) => (
              <span key={crumb.slug}>
                <span className="crumb-sep" aria-hidden="true">
                  ›
                </span>
                <Link to={pagePath(ws, crumb.slug)}>{crumb.title}</Link>
              </span>
            ))}
            <span className="crumb-sep" aria-hidden="true">
              ›
            </span>
            <span className="crumb-current">{view.title}</span>
          </nav>

          <h1>{view.title}</h1>

          <div className="page-actions">
            <Link className="btn" to={pagePath(ws, slug, '/edit')}>
              {t('edit')}
            </Link>
            <Link className="btn" to={newPagePath(ws, slug)}>
              {t('new_subpage')}
            </Link>
            <Link className="btn" to={pagePath(ws, slug, '/history')}>
              {t('history')}
            </Link>
            <button className="btn btn-danger" type="button" onClick={onDelete}>
              {t('delete')}
            </button>
          </div>

          <p className="meta">
            {t('updated')} {updatedDate}
            {editor && (
              <>
                <span className="crumb-sep" aria-hidden="true">
                  ·
                </span>{' '}
                {t('by')} {editor}
              </>
            )}
          </p>
        </header>

        <Markdown ref={proseRef} text={view.content} />

        {view.children.length > 0 && (
          <section className="subpages">
            <div className="subpages-hd">
              <span className="subpages-eyebrow">{t('subpages')}</span>
              <Link className="btn btn-sm" to={newPagePath(ws, slug)}>
                {t('new_short')}
              </Link>
            </div>
            <div className="subpages-grid">
              {view.children.map((child) => (
                <Link className="subpage-card" key={child.slug} to={pagePath(ws, child.slug)}>
                  <div className="subpage-info">
                    <span className="subpage-name">{child.title}</span>
                    <span className="subpage-date">
                      {child.updated_at ? child.updated_at.slice(0, 10) : ''}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          </section>
        )}

        {(view.backlinks.length > 0 || view.related.length > 0) && (
          <section className="relations">
            {view.backlinks.length > 0 && (
              <div className="relations-group">
                <span className="subpages-eyebrow">{t('referenced_by')}</span>
                <ul className="relations-list">
                  {view.backlinks.map((b) => (
                    <li key={b.slug}>
                      <Link to={pagePath(ws, b.slug)}>{b.title}</Link>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {view.related.length > 0 && (
              <div className="relations-group">
                <span className="subpages-eyebrow">{t('related')}</span>
                <ul className="relations-list">
                  {view.related.map((r) => (
                    <li key={r.slug}>
                      <Link to={pagePath(ws, r.slug)}>{r.title}</Link>
                      <span className="relations-meta">{r.shared_tags}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}
      </article>

      <Toc proseRef={proseRef} wrapRef={wrapRef} content={view.content} />
    </div>
  )
}
