import { useI18n } from '../i18n.jsx'
import { useToast } from './Toast.jsx'

// With two languages it is a toggle: it shows the other language's code. Its own class,
// not theme-toggle, so selectors hit the right control.
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
