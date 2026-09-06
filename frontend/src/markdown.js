import MarkdownIt from 'markdown-it'
import taskLists from 'markdown-it-task-lists'
import DOMPurify from 'dompurify'
import { APP_BASE } from './config.js'
import { newPageWithTitlePath, pagePath } from './routes.js'

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

// ── Wikilinks ────────────────────────────────────────────────────────────────
// `[[destino]]` y `[[destino|texto]]` se convierten en anclas a la página. El
// servidor lleva desde siempre estas aristas en `page_links`; lo que faltaba era
// que el lector pudiera seguirlas.
//
// La regla emite tokens (`link_open` / `text` / `link_close`) y no una cadena de
// HTML. La diferencia no es de estilo: pegar un destino sacado del documento
// dentro de `<a href="...">` es exactamente la forma del XSS almacenado que cerró
// el change 001. Como token, el destino es un valor de atributo que markdown-it
// escapa y el saneador ve un ancla normal.
//
// El href se construye siempre como prefijo de ruta más un segmento codificado,
// así que un destino como `javascript:alert(1)` acaba siendo la ruta relativa
// `/w/<ws>/p/javascript%3Aalert(1)` y no un esquema ejecutable.
function wikilinkPlugin(instance) {
  instance.inline.ruler.before('link', 'doction_wikilink', (state, silent) => {
    const start = state.pos
    if (state.src.charCodeAt(start) !== 0x5b || state.src.charCodeAt(start + 1) !== 0x5b) {
      return false
    }
    const end = state.src.indexOf(']]', start + 2)
    if (end === -1) return false

    const inner = state.src.slice(start + 2, end)
    // Un wikilink no cruza líneas ni anida corchetes: sin esto, un `[` suelto
    // dentro se comería el resto del párrafo.
    if (inner.includes('\n') || inner.includes('[')) return false

    const bar = inner.indexOf('|')
    const target = (bar === -1 ? inner : inner.slice(0, bar)).trim()
    const label = (bar === -1 ? '' : inner.slice(bar + 1).trim()) || target
    if (!target) return false

    // Sin workspace no hay ruta que construir. Se deja pasar como texto, que es
    // lo que se veía antes de existir esta regla.
    const ws = state.env && state.env.ws
    if (!ws) return false

    if (!silent) {
      // `slugs` puede no estar (el árbol aún cargando): entonces no se afirma que
      // falte nada. Marcar de rojo una página que sí existe es peor que no marcar.
      const slugs = state.env.slugs
      const missing = slugs ? !slugs.has(target) : false
      // Con APP_BASE por delante: los ayudantes de routes.js devuelven la ruta
      // que espera <Link>, a la que el router le pone el basename. Aquí sale un
      // <a href> de verdad dentro del HTML del documento, y sin el prefijo el
      // navegador lo pide al backend, que no sirve la SPA en esa ruta.
      const href = missing
        ? newPageWithTitlePath(ws, target)
        : pagePath(ws, encodeURIComponent(target))
      const open = state.push('link_open', 'a', 1)
      open.attrs = [
        ['href', APP_BASE + href],
        ['class', missing ? 'wikilink wikilink--missing' : 'wikilink'],
      ]
      const text = state.push('text', '', 0)
      text.content = label
      state.push('link_close', 'a', -1)
    }
    state.pos = end + 2
    return true
  })
}
md.use(wikilinkPlugin)

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

// Un bloque de frontmatter al principio del documento no es prosa: es metadato de
// la página. Y markdown-it no lo sabe — para él `type: runbook` seguido de `---` es
// un encabezado setext, así que la vista de lectura enseñaba «type: runbook owner:
// sre» como si fuera un título de sección.
//
// Se recorta antes de renderizar y no en el servidor: la API devuelve el markdown
// tal cual está guardado, que es lo que el editor edita y lo que `read_page_raw`
// promete a un agente. El frontmatter sigue ahí; lo que cambia es que no se pinta.
const FRONTMATTER = /^---[ \t]*\r?\n[\s\S]*?\r?\n---[ \t]*(?:\r?\n|$)/

function stripFrontmatter(text) {
  return text.replace(FRONTMATTER, '')
}

// `env` lleva el contexto que una regla necesita y el markdown no tiene: el
// workspace al que pertenece el documento y los slugs que existen en él.
export function renderMarkdown(text, env = {}) {
  return DOMPurify.sanitize(md.render(stripFrontmatter(text || ''), env), {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    ALLOWED_URI_REGEXP: ALLOWED_URI,
    // El contenido de un <script> o un <style> se va con la etiqueta: dejarlo
    // convertiría el código en un párrafo de texto suelto en mitad del documento.
    FORBID_CONTENTS: ['script', 'style', 'template'],
  })
}
