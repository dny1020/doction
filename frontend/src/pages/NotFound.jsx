import { Link, useLocation } from 'react-router-dom'
import { useI18n } from '../i18n.jsx'
import { useDocumentTitle } from '../useDocumentTitle.js'

// `standalone` is for routes falling outside the shell, where there is no sidebar around
// it: the page centres as a whole rather than sitting against the content area's edge.
export default function NotFound({ standalone }) {
  const { t } = useI18n()
  const location = useLocation()
  useDocumentTitle(t('nf_title'), null)

  return (
    <div className={'placeholder' + (standalone ? ' placeholder--standalone' : '')}>
      <h1>{t('nf_title')}</h1>
      <p className="muted">
        {t('nf_desc')} <code>{location.pathname}</code>
      </p>
      <Link className="btn btn-primary" to="/">
        {t('back_home')}
      </Link>
    </div>
  )
}
