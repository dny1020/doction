import { useState } from 'react'
import { Moon, Sun } from 'lucide-react'
import { useI18n } from '../i18n.jsx'
import { getTheme, toggleTheme } from '../theme.js'

// Shows the theme it switches to, as doction.site's header does with the same icons.
export default function ThemeToggle() {
  const { t } = useI18n()
  const [theme, setTheme] = useState(getTheme())

  return (
    <button
      className="theme-toggle"
      type="button"
      onClick={() => setTheme(toggleTheme())}
      title={t('toggle_theme')}
      aria-label={t('toggle_theme')}
    >
      {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
    </button>
  )
}
