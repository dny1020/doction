import { Link, useLocation } from 'react-router-dom'
import { useI18n } from '../i18n.jsx'

// 404 con estilo: antes cualquier URL desconocida redirigía a la home en silencio.
export default function NotFound() {
  const { t } = useI18n()
  const location = useLocation()

  return (
    <div className="placeholder">
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
