import { Link, useLocation } from 'react-router-dom'
import { useI18n } from '../i18n.jsx'
import { useDocumentTitle } from '../useDocumentTitle.js'

// 404 con estilo: antes cualquier URL desconocida redirigía a la home en silencio.
//
// `standalone` es para las rutas que caen fuera del shell (una URL que no casa con
// nada): ahí no hay barra lateral alrededor, así que se centra como página entera
// en vez de quedarse pegada al borde del hueco de contenido.
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
