import { useEffect, useState } from 'react'
import { useI18n } from '../../i18n.jsx'
import { useToast } from '../../components/Toast.jsx'
import { getTheme, toggleTheme } from '../../theme.js'

// Theme and language. The same controls also live in the sidebar footer — they are used
// too often to sit two levels in — so both write the same state.
export default function PreferencesSection() {
  const { t, lang, langs, setLang } = useI18n()
  const toast = useToast()
  const [theme, setThemeState] = useState(getTheme)

  // The sidebar footer writes data-theme on <html> directly, bypassing this state.
  // Without observing that attribute, this section kept announcing the old theme.
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
    <section className="card">
      <h2 className="card-title">{t('sec_preferences')}</h2>
      <p className="card-desc">{t('preferences_desc')}</p>

      <div className="row">
        <span className="row-name">{t('theme')}</span>
        <button className="btn" type="button" onClick={onToggleTheme}>
          {theme === 'dark' ? t('theme_dark') : t('theme_light')}
        </button>
      </div>

      <div className="row">
        <span className="row-name">{t('language')}</span>
        <div className="row-actions">
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
