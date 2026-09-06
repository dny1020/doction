import { forwardRef, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { renderMarkdown } from '../markdown.js'
import { enhanceProse } from '../prose.js'
import { APP_BASE } from '../config.js'

// Renderiza markdown a HTML y lo pinta dentro de un contenedor .prose (los
// estilos de lectura del design system). El HTML embebido se admite y lo limpia
// el saneador de lista blanca de markdown.js; nada llega crudo al DOM.
// Tras pintar, mejora el contenido (resaltado de código + diagramas Mermaid).
// El ref se reenvía al div .prose para que el Reader pueda generar el TOC
// a partir de los headings ya pintados en el DOM.
//
// `ws` y `slugs` son lo que necesitan los wikilinks para saber a dónde apuntan y
// si el destino existe.
const Markdown = forwardRef(function Markdown({ text, ws, slugs }, ref) {
  const navigate = useNavigate()

  useEffect(() => {
    enhanceProse(ref.current)
  }, [text, ref])

  // Un wikilink es un <a href> dentro del HTML del documento, no un <Link>, así
  // que por su cuenta recarga la aplicación entera. Se intercepta el clic normal
  // y se enruta en el cliente; se dejan pasar los que el usuario pide abrir de
  // otra forma —rueda, nueva pestaña, guardar— porque ahí el href es lo correcto.
  function onClick(event) {
    const link = event.target.closest?.('a.wikilink')
    if (!link) return
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return
    }
    const href = link.getAttribute('href')
    if (!href || !href.startsWith(APP_BASE + '/')) return
    event.preventDefault()
    navigate(href.slice(APP_BASE.length))
  }

  const html = useMemo(() => renderMarkdown(text, { ws, slugs }), [text, ws, slugs])
  return (
    <div ref={ref} className="prose" onClick={onClick} dangerouslySetInnerHTML={{ __html: html }} />
  )
})

export default Markdown
