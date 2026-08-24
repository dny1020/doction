import { useEffect, useState } from 'react'
import { useI18n } from '../../i18n.jsx'
import { useToast } from '../../components/Toast.jsx'
import { getTheme, toggleTheme } from '../../theme.js'

// Preferencias: tema e idioma. Los mismos controles siguen estando en el pie de la
// barra lateral — se usan demasiado a menudo para vivir solo dos niveles adentro—,
// así que ambos escriben sobre el mismo estado y se ven reflejados el uno al otro.
export default function PreferencesSection() {
  const { t, lang, langs, setLang } = useI18n()
  const toast = useToast()
  const [theme, setThemeState] = useState(getTheme)

  // El tema también se cambia desde el pie de la barra lateral, y allí no pasa por
  // este estado: se escribe directo en data-theme del <html>. Sin observar ese
  // atributo, esta sección seguía anunciando el tema anterior hasta recargar.
  useEffect(() => {
    const observer = new MutationObserver(() => setThemeState(getTheme()))
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    })
    return () => observer.disconnect()
  }, [])

  function onToggleTheme() {
    setThemeState(toggleTheme())
  }

  function onSetLang(code) {
    setLang(code).catch((e) => toast(e.message, 'error'))
  }

  return (
    <section className="settings-card">
      <h2 className="settings-card-title">{t('sec_preferences')}</h2>
      <p className="settings-card-desc">{t('preferences_desc')}</p>

      <div className="settings-row">
        <span className="settings-row-label">{t('theme')}</span>
        <button className="btn" type="button" onClick={onToggleTheme}>
          {theme === 'dark' ? t('theme_dark') : t('theme_light')}
        </button>
      </div>

      <div className="settings-row">
        <span className="settings-row-label">{t('language')}</span>
        <div className="settings-row-actions">
          {langs.map((code) => (
            <button
              key={code}
              className={'btn' + (code === lang ? ' btn-primary' : '')}
              type="button"
              aria-pressed={code === lang}
              onClick={() => onSetLang(code)}
            >
              {code.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
    </section>
  )
}
