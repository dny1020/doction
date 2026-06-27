import MarkdownIt from 'markdown-it'

// Misma configuración que el servidor (app/markdown.py): CommonMark, sin HTML
// crudo (html:false cierra el XSS almacenado), con autoenlaces, tipografía,
// tablas y tachado. Así el render del cliente coincide con el del backend.
const md = new MarkdownIt('commonmark', {
  html: false,
  linkify: true,
  typographer: true,
})
md.enable(['table', 'strikethrough'])

export function renderMarkdown(text) {
  return md.render(text || '')
}
