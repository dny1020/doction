import React from 'react'
import { renderMarkdown } from '../markdown.js'

// Renderiza markdown a HTML y lo pinta dentro de un contenedor .prose
// (los estilos de lectura del design system). Es seguro porque markdown-it
// va con html:false: nunca inserta HTML escrito por el usuario.
export default function Markdown({ text }) {
  return <div className="prose" dangerouslySetInnerHTML={{ __html: renderMarkdown(text) }} />
}
