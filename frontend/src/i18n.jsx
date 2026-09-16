import { createContext, useContext, useEffect, useState } from 'react'
import { api } from './api.js'

// Internationalization (EN/ES). The catalogue lives in the backend (app/i18n.py) and is
// served over /api/i18n, so the SPA does not duplicate the translations. `t(key)` returns
// the text, or the key itself when it is missing, so the interface never breaks.

const I18nContext = createContext(null)

// Boot catalogue: only "loading" is needed until the real one arrives.
const BOOT = { lang: 'en', langs: ['en', 'es'], t: { loading: 'Loading…' } }

export function I18nProvider({ children }) {
  const [data, setData] = useState(BOOT)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    api
      .get('/api/i18n')
      .then(setData)
      .catch(() => setData(BOOT))
      .finally(() => setReady(true))
  }, [])

  // index.html hardcodes lang="en"; without this a screen reader would read the Spanish
  // interface with English rules.
  useEffect(() => {
    document.documentElement.lang = data.lang
  }, [data.lang])

  function t(key) {
    return data.t[key] || key
  }

  async function setLang(code) {
    if (code === data.lang) return
    await api.post('/api/lang/' + code)
    const fresh = await api.get('/api/i18n')
    setData(fresh) // re-renderiza toda la app en el nuevo idioma, sin recargar
  }

  // Wait for the catalogue, so the raw keys never flash on screen.
  if (!ready) return <div className="placeholder">{BOOT.t.loading}</div>

  const value = { lang: data.lang, langs: data.langs, t, setLang }
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  return useContext(I18nContext)
}
