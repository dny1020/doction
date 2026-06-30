// Mejora client-side de la vista de lectura (.prose): diagramas Mermaid y
// resaltado de sintaxis. Equivale a app/static/prose.js del frontend Jinja:
// ambas librerías están vendadas (servidas en /static/vendor) y se cargan de
// forma perezosa solo si la página las necesita, así no hay coste sin código
// ni diagramas. El CSS de highlight.js ya vive en static/style.css.

const loaded = {} // cache de promesas por src, para no cargar dos veces

function loadScript(src) {
  if (loaded[src]) return loaded[src]
  loaded[src] = new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.src = src
    s.defer = true
    s.onload = resolve
    s.onerror = reject
    document.head.appendChild(s)
  })
  return loaded[src]
}

// Convierte los bloques ```mermaid en <div class="mermaid"> y los renderiza.
function renderMermaid(root) {
  const blocks = root.querySelectorAll('pre > code.language-mermaid')
  if (!blocks.length) return
  blocks.forEach((code) => {
    const div = document.createElement('div')
    div.className = 'mermaid'
    div.textContent = code.textContent
    code.closest('pre').replaceWith(div)
  })
  loadScript('/static/vendor/mermaid.min.js')
    .then(() => {
      if (typeof mermaid === 'undefined') return
      const dark = document.documentElement.getAttribute('data-theme') === 'dark'
      mermaid.initialize({ startOnLoad: false, theme: dark ? 'dark' : 'default', securityLevel: 'strict' })
      mermaid.run({ nodes: root.querySelectorAll('.mermaid') })
    })
    .catch(() => {})
}

// Resalta los bloques de código con clase de lenguaje (menos mermaid).
function highlightCode(root) {
  const blocks = root.querySelectorAll('pre > code[class*="language-"]:not(.language-mermaid)')
  if (!blocks.length) return
  loadScript('/static/vendor/highlight.min.js')
    .then(() => {
      if (typeof hljs === 'undefined') return
      blocks.forEach((block) => hljs.highlightElement(block))
    })
    .catch(() => {})
}

// Mejora un contenedor .prose ya pintado (llamar tras inyectar el HTML).
export function enhanceProse(root) {
  if (!root) return
  renderMermaid(root)
  highlightCode(root)
}
