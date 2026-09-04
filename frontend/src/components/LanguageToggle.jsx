import { useI18n } from '../i18n.jsx'
import { useToast } from './Toast.jsx'

// Botón para cambiar de idioma. Con dos idiomas funciona como interruptor: muestra
// el código del OTRO idioma y al pulsarlo cambia a él.
//
// Clase propia aunque comparta el aspecto con el de tema: llevaba `theme-toggle` y
// eso hacía que un selector por esa clase acertara el control equivocado. Comparten
// estilo por lista de selectores, no por nombre.
export default function LanguageToggle({ className = 'lang-toggle' }) {
  const { lang, langs, setLang, t } = useI18n()
  const toast = useToast()

  // El siguiente idioma de la lista (vuelve al principio al llegar al final).
  const nextLang = langs[(langs.indexOf(lang) + 1) % langs.length]

  return (
    <button
      className={className}
      type="button"
      onClick={() => setLang(nextLang).catch((e) => toast(e.message, 'error'))}
      title={t('language')}
    >
      {nextLang.toUpperCase()}
    </button>
  )
}
