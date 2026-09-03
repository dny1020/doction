import MarkdownIt from 'markdown-it'
import taskLists from 'markdown-it-task-lists'
import DOMPurify from 'dompurify'

// El render de markdown vive solo en el cliente: el backend guarda markdown crudo y
// no renderiza nada, así que cada decisión de aquí es un límite de seguridad.
//
// Antes esto corría con `html: false`, que cerraba el XSS a base de no renderizar
// HTML en absoluto. Era seguro y también la razón de que una lista de tareas
// saliera como `- [ ]` literal y de que un `<details>` pegado de otro sitio
// desapareciera sin decir nada. Ahora el HTML entra y sale por un saneador con
// lista blanca: las dos mitades del cambio van juntas, porque habilitar una sin la
// otra es exactamente cómo se publica un XSS almacenado.

// ── Lista blanca ─────────────────────────────────────────────────────────────
// Es de doction y no la de la librería a propósito: lo que se renderiza es una
// decisión del producto, y heredarla en silencio significa que la próxima versión
// de la dependencia la cambie por nosotros.
const ALLOWED_TAGS = [
  // Estructura de un documento markdown.
  'p',
  'br',
  'hr',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'ul',
  'ol',
  'li',
  'dl',
  'dt',
  'dd',
  'blockquote',
  'pre',
  'code',
  'table',
  'thead',
  'tbody',
  'tfoot',
  'tr',
  'th',
  'td',
  'a',
  'img',
  'figure',
  'figcaption',
  // Inline con significado, que es para lo que se abre el HTML embebido.
  'strong',
  'em',
  'del',
  's',
  'ins',
  'mark',
  'sub',
  'sup',
  'small',
  'abbr',
  'kbd',
  'samp',
  'var',
  'q',
  'cite',
  'time',
  'span',
  'div',
  'details',
  'summary',
  // Solo por las casillas de las listas de tareas; ver el hook de abajo.
  'input',
]

const ALLOWED_ATTR = [
  'href',
  'src',
  'alt',
  'title',
  'class',
  'lang',
  'dir',
  'colspan',
  'rowspan',
  'align',
  'start',
  'reversed',
  'datetime',
  'type',
  'checked',
  'disabled',
]

// Esquemas de URL admitidos: http(s), mailto, tel y cualquier cosa sin esquema
// (relativa, ancla). Deja fuera `javascript:` y `data:` — la primera ejecuta y la
// segunda es un documento entero metido en un atributo.
const ALLOWED_URI = /^(?:(?:https?|mailto|tel):|[^a-z]|[a-z+.-]+(?:[^a-z+.:-]|$))/i

// `input` está en la lista solo por `- [x]`. Cualquier otro se va: una página no
// tiene por qué poder pintar un campo de texto dentro de un documento.
DOMPurify.addHook('uponSanitizeElement', (node, data) => {
  if (data.tagName !== 'input') return
  const checkbox = node.getAttribute('type') === 'checkbox' && node.hasAttribute('disabled')
  if (!checkbox) node.remove()
})

const md = new MarkdownIt('commonmark', {
  html: true,
  linkify: true,
  typographer: true,
})
md.enable(['table', 'strikethrough'])
// Las casillas se pintan deshabilitadas: la vista de lectura lee, no edita. El
// estado de una tarea se cambia editando el markdown, que es donde vive.
md.use(taskLists, { enabled: false, label: false })

// ── Matemáticas ──────────────────────────────────────────────────────────────
// `$…$` y `$$…$$` se marcan aquí y los pinta KaTeX más tarde (prose.js), igual que
// los diagramas de Mermaid: así los 600 KB de KaTeX solo se descargan en las
// páginas que llevan fórmulas. Se emite el origen como texto dentro de un nodo
// marcado, de modo que lo que pasa por el saneador es texto y nunca markup.
function mathPlugin(instance) {
  instance.inline.ruler.before('escape', 'doction_math', (state, silent) => {
    const start = state.pos
    if (state.src[start] !== '$') return false
    const block = state.src[start + 1] === '$'
    const fence = block ? '$$' : '$'
    const from = start + fence.length
    const end = state.src.indexOf(fence, from)
    if (end === -1) return false
    const body = state.src.slice(from, end)
    // `$10 y $20` no son matemáticas: sin contenido, o abriendo con un espacio, se
    // deja pasar como texto normal.
    if (!body.trim() || (!block && /^\s|\s$/.test(body))) return false
    if (!silent) {
      const token = state.push('doction_math', 'span', 0)
      token.content = body
      token.markup = fence
    }
    state.pos = end + fence.length
    return true
  })

  instance.renderer.rules.doction_math = (tokens, idx) => {
    const token = tokens[idx]
    const block = token.markup === '$$'
    const tag = block ? 'div' : 'span'
    const cls = block ? 'math math--block' : 'math'
    return `<${tag} class="${cls}">${instance.utils.escapeHtml(token.content)}</${tag}>`
  }
}
md.use(mathPlugin)

// ── Alineación de tablas ─────────────────────────────────────────────────────
// markdown-it escribe la alineación de cada columna como `style` en línea, y el
// saneador quita `style` — con razón: es la vía por la que una página se pinta
// encima del resto de la interfaz. Se traduce a una clase, que sí sobrevive, y la
// alineación pasa a vivir en el CSS, que es donde debería haber estado siempre.
function tableAlignPlugin(instance) {
  for (const rule of ['th_open', 'td_open']) {
    instance.renderer.rules[rule] = (tokens, idx, options, env, self) => {
      const token = tokens[idx]
      const style = token.attrGet('style')
      if (style && style.startsWith('text-align:')) {
        token.attrSet('class', 'align-' + style.slice('text-align:'.length).trim())
        token.attrs = token.attrs.filter(([name]) => name !== 'style')
      }
      return self.renderToken(tokens, idx, options)
    }
  }
}
md.use(tableAlignPlugin)

export function renderMarkdown(text) {
  return DOMPurify.sanitize(md.render(text || ''), {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    ALLOWED_URI_REGEXP: ALLOWED_URI,
    // El contenido de un <script> o un <style> se va con la etiqueta: dejarlo
    // convertiría el código en un párrafo de texto suelto en mitad del documento.
    FORBID_CONTENTS: ['script', 'style', 'template'],
  })
}
