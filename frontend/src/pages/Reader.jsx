import React, { useEffect, useState } from 'react'
import { Link, Navigate, useNavigate, useOutletContext, useParams } from 'react-router-dom'
import { api } from '../api.js'
import { useI18n } from '../i18n.jsx'
import Markdown from '../components/Markdown.jsx'

// Vista de lectura de una página. Pide /api/pages/{slug}/view, que trae el
// contenido + migas + subpáginas + backlinks + relacionadas en una sola llamada.
export default function Reader() {
  const { slug } = useParams()
  const { pages, reloadPages } = useOutletContext()
  const { t } = useI18n()
  const navigate = useNavigate()
  const [view, setView] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!slug) return
    setView(null)
    setError(null)
    api
      .get('/api/pages/' + slug + '/view')
      .then(setView)
      .catch((e) => setError(e.message))
  }, [slug])

  // Ruta home (/): si hay páginas, abre la primera; si no, estado vacío.
  if (!slug) {
    if (pages && pages.length > 0) return <Navigate to={'/p/' + pages[0].slug} replace />
    return (
      <div className="placeholder">
        <h1>{t('empty_title')}</h1>
        <Link className="btn btn-primary" to="/new">
          {t('create_this_page')}
        </Link>
      </div>
    )
  }

  if (error) {
    return (
      <div className="placeholder">
        <h1>{error}</h1>
      </div>
    )
  }
  if (!view) return <div className="placeholder">{t('loading')}</div>

  async function onDelete() {
    if (!window.confirm(t('confirm_delete_page') + ' “' + view.title + '”?')) return
    await api.del('/api/pages/' + slug)
    reloadPages()
    navigate('/')
  }

  const updatedDate = view.updated_at ? view.updated_at.slice(0, 10) : ''
  const editor = view.updated_by_name || view.updated_by_email

  return (
    <div className="page-wrap">
      <article className="page">
        <header className="page-header">
          <nav className="breadcrumbs" aria-label="Breadcrumb">
            <Link to="/">{t('home')}</Link>
            {view.breadcrumbs.map((crumb) => (
              <span key={crumb.slug}>
                <span className="crumb-sep" aria-hidden="true">›</span>
                <Link to={'/p/' + crumb.slug}>{crumb.title}</Link>
              </span>
            ))}
            <span className="crumb-sep" aria-hidden="true">›</span>
            <span className="crumb-current">{view.title}</span>
          </nav>

          <h1>{view.title}</h1>

          <div className="page-actions">
            <Link className="btn" to={'/p/' + slug + '/edit'}>{t('edit')}</Link>
            <Link className="btn" to={'/new?parent=' + slug}>{t('new_subpage')}</Link>
            <Link className="btn" to={'/p/' + slug + '/history'}>{t('history')}</Link>
            <button className="btn btn-danger" type="button" onClick={onDelete}>{t('delete')}</button>
          </div>

          <p className="meta">
            {t('updated')} {updatedDate}
            {editor && (
              <>
                <span className="crumb-sep" aria-hidden="true">·</span> {t('by')} {editor}
              </>
            )}
          </p>
        </header>

        <Markdown text={view.content} />

        {view.children.length > 0 && (
          <section className="subpages">
            <div className="subpages-hd">
              <span className="subpages-eyebrow">{t('subpages')}</span>
              <Link className="btn btn-sm" to={'/new?parent=' + slug}>{t('new_short')}</Link>
            </div>
            <div className="subpages-grid">
              {view.children.map((child) => (
                <Link className="subpage-card" key={child.slug} to={'/p/' + child.slug}>
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
                      <Link to={'/p/' + b.slug}>{b.title}</Link>
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
                      <Link to={'/p/' + r.slug}>{r.title}</Link>
                      <span className="relations-meta">{r.shared_tags}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}
      </article>
    </div>
  )
}
