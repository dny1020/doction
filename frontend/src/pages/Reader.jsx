import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, Navigate, useNavigate, useOutletContext, useParams } from 'react-router-dom'
import { api, isAbort } from '../api.js'
import { useI18n } from '../i18n.jsx'
import { newPagePath, pagePath, wsPath } from '../routes.js'
import { useToast } from '../components/Toast.jsx'
import { useConfirm } from '../components/ConfirmDialog.jsx'
import Markdown from '../components/Markdown.jsx'
import Toc from '../components/Toc.jsx'
import EmptyState from '../components/EmptyState.jsx'
import { DocumentSkeleton } from '../components/Skeleton.jsx'
import { useDocumentTitle } from '../useDocumentTitle.js'

// A page's reading view. /api/pages/{slug}/view brings content, breadcrumbs, children,
// backlinks and related pages in one call.
export default function Reader() {
  const { slug } = useParams()
  const { ws, pages, pagesReady, pagesError, reloadPages, setTitleOffscreen } = useOutletContext()
  const { t } = useI18n()
  const navigate = useNavigate()
  const toast = useToast()
  const confirm = useConfirm()
  const [view, setView] = useState(null)
  const [error, setError] = useState(null) // api.js Error (carries .status)
  // The button is disabled while the delete is in flight, so two clicks are not two
  // deletes.
  const [deleting, setDeleting] = useState(false)
  // Wikilinks need the set of existing slugs to tell a link from one that leads nowhere
  // yet. The Layout already has the tree.
  const slugSet = useMemo(() => new Set(pages.map((p) => p.slug)), [pages])
  const wrapRef = useRef(null)
  const proseRef = useRef(null)
  const titleRef = useRef(null)

  // The AbortController lives in a ref so `load` can retry without leaving the previous
  // request hanging.
  const requestRef = useRef(null)

  const load = useCallback(() => {
    if (!slug || !ws) return undefined
    requestRef.current?.abort()
    const controller = new AbortController()
    requestRef.current = controller
    setView(null)
    setError(null)
    api
      .get('/api/pages/' + slug + '/view', controller.signal)
      .then(setView)
      .catch((e) => {
        // Cancelled because we are already going elsewhere: nothing to show.
        if (!isAbort(e)) setError(e)
      })
    return () => controller.abort()
    // `ws` matters: the same slug in another workspace is another page.
  }, [slug, ws])

  useEffect(load, [load])

  useDocumentTitle(view ? view.title : null, ws)

  // The top bar shows the title only once this one has scrolled under it, so a page
  // never says its name twice on one screen. The bar's height is the top margin.
  useEffect(() => {
    const title = titleRef.current
    if (!title) return undefined
    const barHeight = document.querySelector('.app-bar')?.offsetHeight ?? 0
    const observer = new IntersectionObserver(
      ([entry]) => setTitleOffscreen(!entry.isIntersecting),
      { rootMargin: `-${barHeight}px 0px 0px 0px` },
    )
    observer.observe(title)
    return () => {
      observer.disconnect()
      setTitleOffscreen(false)
    }
  }, [view, setTitleOffscreen])

  // The home route opens the first page, or the empty state — unless the tree failed to
  // load, since a dead network is not an empty workspace.
  if (!slug) {
    // Nothing is decided without *this* workspace's tree: redirecting with the previous
    // one sends you to a page that does not exist here.
    if (!pagesReady && !pagesError) return <DocumentSkeleton />
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
      <EmptyState
        title={t('empty_title')}
        hint={t('empty_workspace_hint')}
        actionLabel={t('create_this_page')}
        actionTo={newPagePath(ws)}
      />
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
  if (!view) return <DocumentSkeleton />

  async function onDelete() {
    if (deleting) return
    let message = t('confirm_delete_page') + ' “' + view.title + '”?'
    // A page takes its children with it. Say so first, not after.
    if (view.children.length > 0) {
      message += ' ' + t('confirm_delete_children').replace('{n}', view.children.length)
    }
    if (!(await confirm(message, { confirmLabel: t('delete'), danger: true }))) return
    setDeleting(true)
    try {
      await api.del('/api/pages/' + slug)
    } catch (e) {
      toast(e.message, 'error')
      setDeleting(false)
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

          <h1 ref={titleRef}>{view.title}</h1>

          <div className="page-header-foot">
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

            <div className="page-actions">
              <Link className="btn btn-sm" to={pagePath(ws, slug, '/edit')}>
                {t('edit')}
              </Link>
              <Link className="btn btn-sm" to={newPagePath(ws, slug)}>
                {t('new_subpage')}
              </Link>
              <Link className="btn btn-sm" to={pagePath(ws, slug, '/history')}>
                {t('history')}
              </Link>
              <button
                className="btn btn-sm btn-danger"
                type="button"
                onClick={onDelete}
                disabled={deleting}
              >
                {t('delete')}
              </button>
            </div>
          </div>
        </header>

        {view.content.trim() ? (
          <Markdown ref={proseRef} text={view.content} ws={ws} slugs={slugSet} />
        ) : (
          <div className="prose" ref={proseRef}>
            <p className="muted">{t('empty_page')}</p>
            <Link className="btn btn-sm" to={pagePath(ws, slug, '/edit')}>
              {t('edit')}
            </Link>
          </div>
        )}

        {view.children.length > 0 && (
          <section className="subpages">
            <div className="subpages-hd">
              <span className="eyebrow">{t('subpages')}</span>
              <Link className="btn btn-sm" to={newPagePath(ws, slug)}>
                {t('new_short')}
              </Link>
            </div>
            <div className="subpages-grid">
              {view.children.map((child) => (
                <Link className="card subpage-card" key={child.slug} to={pagePath(ws, child.slug)}>
                  <div className="row-name">
                    <span className="row-title">{child.title}</span>
                    <span className="meta">
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
                <span className="eyebrow">{t('referenced_by')}</span>
                <ul className="rows">
                  {view.backlinks.map((b) => (
                    <li className="row" key={b.slug}>
                      <div className="row-name">
                        <Link to={pagePath(ws, b.slug)}>{b.title}</Link>
                        {b.context?.length > 0 && (
                          <p className="snippet">
                            {b.context.map((part, i) =>
                              part.match ? <mark key={i}>{part.text}</mark> : part.text,
                            )}
                          </p>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {view.related.length > 0 && (
              <div className="relations-group">
                <span className="eyebrow">{t('related')}</span>
                <ul className="rows">
                  {view.related.map((r) => (
                    <li className="row" key={r.slug}>
                      <span className="row-name">
                        <Link to={pagePath(ws, r.slug)}>{r.title}</Link>
                      </span>
                      <span className="meta">{r.shared_tags}</span>
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
