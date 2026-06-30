import React from 'react'
import { useI18n } from '../i18n.jsx'

// Botón para cambiar de idioma. Con dos idiomas funciona como interruptor: muestra
// el código del OTRO idioma y al pulsarlo cambia a él. Reusa el estilo de los demás
// controles (theme-toggle) para integrarse en la barra lateral o en el login.
export default function LanguageToggle({ className = 'theme-toggle' }) {
  const { lang, langs, setLang, t } = useI18n()

  // El siguiente idioma de la lista (vuelve al principio al llegar al final).
  const nextLang = langs[(langs.indexOf(lang) + 1) % langs.length]

  return (
    <button
      className={className}
      type="button"
      onClick={() => setLang(nextLang)}
      title={t('language')}
    >
      {nextLang.toUpperCase()}
    </button>
  )
}
