import React, { createContext, useContext, useEffect, useState } from 'react'
import { api } from './api.js'

// Internacionalización (EN/ES). El catálogo vive en el backend (app/i18n.py) y lo
// servimos por /api/i18n, así que la SPA no duplica las traducciones: las pide una
// vez según el idioma activo (cookie `lang`). t('clave') devuelve el texto, o la
// propia clave si faltara, para que nunca se rompa la interfaz.

const I18nContext = createContext(null)

// Catálogo mínimo de arranque: solo necesitamos "loading" hasta que llega el real.
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

  function t(key) {
    return data.t[key] || key
  }

  async function setLang(code) {
    if (code === data.lang) return
    await api.post('/api/lang/' + code)
    const fresh = await api.get('/api/i18n')
    setData(fresh) // re-renderiza toda la app en el nuevo idioma, sin recargar
  }

  // Esperamos al catálogo para no mostrar las claves en crudo un instante.
  if (!ready) return <div className="placeholder">{BOOT.t.loading}</div>

  const value = { lang: data.lang, langs: data.langs, t, setLang }
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  return useContext(I18nContext)
}
