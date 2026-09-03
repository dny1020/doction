import { useEffect } from 'react'

// El título de la pestaña era la cadena fija «doction», escrita en index.html y
// nunca reescrita: diez pestañas abiertas eran diez pestañas idénticas, y una
// entrada del historial no decía de qué página era.
//
// El orden va de lo específico a lo general —página, workspace, aplicación—, que es
// el que sobrevive al recorte de la pestaña: lo primero que se ve es lo que
// distingue una de otra.
const APP = 'doction'

export function useDocumentTitle(page, workspace) {
  useEffect(() => {
    const parts = [page, workspace].filter(Boolean)
    // textContent y no innerHTML: `document.title` es texto por definición, así que
    // un título con caracteres significativos en HTML sale literal.
    document.title = parts.length > 0 ? parts.join(' | ') + ' — ' + APP : APP
    return () => {
      document.title = APP
    }
  }, [page, workspace])
}
