import React, { forwardRef, useEffect } from 'react'
import { renderMarkdown } from '../markdown.js'
import { enhanceProse } from '../prose.js'

// Renderiza markdown a HTML y lo pinta dentro de un contenedor .prose
// (los estilos de lectura del design system). Es seguro porque markdown-it
// va con html:false: nunca inserta HTML escrito por el usuario.
// Tras pintar, mejora el contenido (resaltado de código + diagramas Mermaid).
// El ref se reenvía al div .prose para que el Reader pueda generar el TOC
// a partir de los headings ya pintados en el DOM.
const Markdown = forwardRef(function Markdown({ text }, ref) {
  useEffect(() => {
    enhanceProse(ref.current)
  }, [text, ref])

  return (
    <div
      ref={ref}
      className="prose"
      dangerouslySetInnerHTML={{ __html: renderMarkdown(text) }}
    />
  )
})

export default Markdown
