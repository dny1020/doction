import MarkdownIt from 'markdown-it'

// El render de markdown vive solo en el cliente (el backend guarda markdown
// crudo): CommonMark, sin HTML crudo (html:false cierra el XSS almacenado),
// con autoenlaces, tipografía, tablas y tachado.
const md = new MarkdownIt('commonmark', {
  html: false,
  linkify: true,
  typographer: true,
})
md.enable(['table', 'strikethrough'])

export function renderMarkdown(text) {
  return md.render(text || '')
}
