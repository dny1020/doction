import { useEffect, useState } from 'react'
import { api } from '../../api.js'
import { useI18n } from '../../i18n.jsx'

// Sistema: qué está corriendo el despliegue. Todo es de solo lectura —las banderas
// salen del entorno del servidor—, así que se pinta como filas de datos y no como
// controles. Existe porque hasta ahora no había forma de saber en qué modo de
// búsqueda estaba un servidor salvo mirando la forma de los resultados.
export default function SystemSection() {
  const { t } = useI18n()
  const [report, setReport] = useState(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    api
      .get('/api/system')
      .then(setReport)
      .catch(() => setFailed(true))
  }, [])

  if (failed) {
    return (
      <section className="settings-card">
        <h2 className="settings-card-title">{t('sec_system')}</h2>
        <p className="settings-card-desc">{t('system_unavailable')}</p>
      </section>
    )
  }
  if (!report) {
    return <div className="placeholder">{t('loading')}</div>
  }

  const flag = (on) => (on ? t('enabled') : t('disabled'))

  return (
    <section className="settings-card">
      <h2 className="settings-card-title">{t('sec_system')}</h2>
      <p className="settings-card-desc">{t('system_desc')}</p>

      <h3 className="settings-group-title">{t('system_retrieval')}</h3>
      <dl className="settings-facts">
        <Fact label={t('semantic_search')} value={flag(report.semantic_search)} />
        <Fact label={t('reranker')} value={flag(report.rerank)} />
        <Fact label={t('ocr_uploads')} value={flag(report.ocr_uploads)} />
        {report.embedding_model !== undefined && (
          <Fact label={t('embedding_model')} value={report.embedding_model} />
        )}
        {report.indexed_pages !== undefined && (
          <Fact label={t('indexed_pages')} value={String(report.indexed_pages)} />
        )}
        {report.pending_pages !== undefined && (
          <Fact label={t('pending_pages')} value={String(report.pending_pages)} />
        )}
      </dl>

      <h3 className="settings-group-title">{t('system_server')}</h3>
      <dl className="settings-facts">
        <Fact label={t('version')} value={report.version} />
        <Fact label={t('database')} value={report.db === 'ok' ? t('db_ok') : t('db_unreachable')} />
      </dl>
    </section>
  )
}

function Fact({ label, value }) {
  return (
    <div className="settings-fact">
      <dt className="settings-fact-label">{label}</dt>
      <dd className="settings-fact-value">{value}</dd>
    </div>
  )
}
