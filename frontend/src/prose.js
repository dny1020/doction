// Mejora client-side de la vista de lectura (.prose): diagramas Mermaid, resaltado
// de sintaxis y fórmulas. Las tres librerías están vendorizadas (se sirven desde
// /static/vendor) y se cargan de forma perezosa solo si la página las necesita, así
// que una página sin diagramas, sin código ni fórmulas no descarga nada de esto —
// KaTeX solo pesa 600 KB en las páginas que llevan matemáticas. El CSS de
// highlight.js ya vive en static/style.css; el de KaTeX se inyecta con la librería.

const loaded = {} // cache de promesas por src, para no cargar dos veces

function loadStyle(href) {
  if (loaded[href]) return loaded[href]
  loaded[href] = new Promise((resolve, reject) => {
    const link = document.createElement('link')
    link.rel = 'stylesheet'
    link.href = href
    link.onload = resolve
    link.onerror = reject
    document.head.appendChild(link)
  })
  return loaded[href]
}

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
      mermaid.initialize({
        startOnLoad: false,
        theme: dark ? 'dark' : 'default',
        securityLevel: 'strict',
      })
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

// Pinta las formulas marcadas por el plugin de markdown.js. El markdown deja el
// origen como texto dentro de .math; KaTeX lo convierte aqui, en el cliente, asi
// que su salida no pasa por el saneador — y no hace falta que pase, porque lo que
// entra a KaTeX es texto y lo que sale lo genera KaTeX, no la pagina.
function renderMath(root) {
  const nodes = root.querySelectorAll('.math')
  if (!nodes.length) return
  Promise.all([
    loadScript('/static/vendor/katex/katex.min.js'),
    loadStyle('/static/vendor/katex/katex.min.css'),
  ])
    .then(() => {
      if (typeof katex === 'undefined') return
      nodes.forEach((node) => {
        try {
          katex.render(node.textContent, node, {
            displayMode: node.classList.contains('math--block'),
            // trust:false deja fuera \\href y \\includegraphics, que son las dos
            // macros con las que una formula puede salir de ser una formula.
            trust: false,
            throwOnError: false,
          })
        } catch {
          // Formula invalida: se queda el origen a la vista, que es mas util que
          // un hueco vacio y no rompe el resto del documento.
        }
      })
    })
    .catch(() => {})
}

// Mejora un contenedor .prose ya pintado (llamar tras inyectar el HTML).
export function enhanceProse(root) {
  if (!root) return
  renderMermaid(root)
  highlightCode(root)
  renderMath(root)
}
