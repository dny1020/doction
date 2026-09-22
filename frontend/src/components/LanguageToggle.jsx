import { useI18n } from '../i18n.jsx'
import { useToast } from './Toast.jsx'

// Language switch. With two languages it works as a toggle: it shows the *other*
// language's code and switches to it.
//
// Its own class even though it looks like the theme toggle: it used to carry
// `theme-toggle`, which made a selector on that class hit the wrong control. They share
// styling through a selector list, not through a name.
export default function LanguageToggle({ className = 'lang-toggle' }) {
  const { lang, langs, setLang, t } = useI18n()
  const toast = useToast()

  // The next language in the list, wrapping at the end.
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
