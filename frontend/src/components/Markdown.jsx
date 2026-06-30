import React, { useEffect, useRef } from 'react'
import { renderMarkdown } from '../markdown.js'
import { enhanceProse } from '../prose.js'

// Renderiza markdown a HTML y lo pinta dentro de un contenedor .prose
// (los estilos de lectura del design system). Es seguro porque markdown-it
// va con html:false: nunca inserta HTML escrito por el usuario.
// Tras pintar, mejora el contenido (resaltado de código + diagramas Mermaid).
export default function Markdown({ text }) {
  const ref = useRef(null)

  useEffect(() => {
    enhanceProse(ref.current)
  }, [text])

  return (
    <div
      ref={ref}
      className="prose"
      dangerouslySetInnerHTML={{ __html: renderMarkdown(text) }}
    />
  )
}
