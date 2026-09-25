// Client-side enhancement of the reading view (.prose): Mermaid diagrams, syntax
// highlighting and formulas. All three libraries are vendored under /static/vendor and
// load lazily, so a page with no diagrams, code or math downloads none of them.

const loaded = {} // promise cache per src, so nothing loads twice

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

// Mermaid cannot parse oklch() and fails silently. Neither getComputedStyle nor fillStyle
// normalise it to rgb, so the colour is painted and the pixel read back.
let probe = null
function toRgbHex(value) {
  if (!value || value.startsWith('#')) return value
  if (!probe) {
    const canvas = document.createElement('canvas')
    canvas.width = canvas.height = 1
    probe = canvas.getContext('2d', { willReadFrequently: true })
  }
  try {
    probe.clearRect(0, 0, 1, 1)
    probe.fillStyle = value
    probe.fillRect(0, 0, 1, 1)
    const [r, g, b] = probe.getImageData(0, 0, 1, 1).data
    return '#' + [r, g, b].map((n) => n.toString(16).padStart(2, '0')).join('')
  } catch {
    // If the canvas fails, the original value beats nothing: mermaid falls back to its
    // own colour for that slot and the rest stays the application's.
    return value
  }
}

function token(name) {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return toRgbHex(raw)
}

// Mermaid's variables, taken from the design tokens. Only the ones the engine uses for
// nodes, edges and labels are named; it derives the rest from these.
function mermaidPalette() {
  const ink = token('--ink')
  const line = token('--border-default')
  return {
    background: token('--background'),
    primaryColor: token('--green-soft'),
    primaryTextColor: ink,
    primaryBorderColor: token('--green'),
    secondaryColor: token('--surface-muted'),
    secondaryTextColor: ink,
    secondaryBorderColor: line,
    tertiaryColor: token('--surface'),
    tertiaryTextColor: ink,
    tertiaryBorderColor: line,
    lineColor: line,
    textColor: ink,
    mainBkg: token('--green-soft'),
    nodeBorder: token('--green'),
    nodeTextColor: ink,
    edgeLabelBackground: token('--background'),
    clusterBkg: token('--surface-muted'),
    clusterBorder: token('--border-subtle'),
    titleColor: ink,
  }
}

// Turns ```mermaid blocks into <div class="mermaid"> and renders them.
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
      mermaid.initialize({
        startOnLoad: false,
        // `base` with our tokens, not Mermaid's own themes, so diagrams follow the theme.
        theme: 'base',
        themeVariables: mermaidPalette(),
        fontFamily: token('--font-ui'),
        securityLevel: 'strict',
      })
      mermaid.run({ nodes: root.querySelectorAll('.mermaid') })
    })
    .catch(() => {})
}

// Highlights code blocks that carry a language class, except mermaid.
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

// Paints the formulas markdown.js marked. The markdown leaves the source as text inside
// .math and KaTeX converts it here, so its output never passes through the sanitizer —
// and need not: what goes into KaTeX is text, and what comes out KaTeX generated.
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
            // trust:false excludes \\href and \\includegraphics, the two macros that
            // let a formula stop being a formula.
            trust: false,
            throwOnError: false,
          })
        } catch {
          // An invalid formula leaves its source visible, which beats an empty gap.
        }
      })
    })
    .catch(() => {})
}

// Enhances an already-painted .prose container; call after injecting the HTML.
export function enhanceProse(root) {
  if (!root) return
  renderMermaid(root)
  highlightCode(root)
  renderMath(root)
}
