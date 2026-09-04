import { describe, expect, it } from 'vitest'
import { renderMarkdown } from './markdown.js'

// El saneador es un límite de seguridad, así que se comprueba con tests y no
// mirando una pantalla. Cubre las dos mitades del cambio a la vez: que el HTML
// peligroso no sobreviva, y que habilitarlo no se haya llevado por delante nada
// de lo que el markdown ya pintaba.

describe('HTML embebido', () => {
  it('quita el script y su contenido', () => {
    const html = renderMarkdown('Antes\n\n<script>alert(1)</script>\n\nDespués')
    expect(html).not.toContain('<script')
    expect(html).not.toContain('alert(1)')
    // El documento de alrededor se sigue pintando: no se rechaza entero.
    expect(html).toContain('Antes')
    expect(html).toContain('Después')
  })

  it('quita los manejadores de evento y deja el elemento', () => {
    const html = renderMarkdown('<img src="x" onerror="alert(1)" alt="a">')
    expect(html).toContain('<img')
    expect(html).not.toContain('onerror')
  })

  it.each(['onclick', 'onload', 'onmouseover', 'onfocus'])('quita %s', (handler) => {
    expect(renderMarkdown(`<div ${handler}="alert(1)">hola</div>`)).not.toContain(handler)
  })

  it('desactiva las URL javascript:, escritas como enlace o como HTML', () => {
    // markdown-it ya rechaza el esquema y no llega a construir el enlace…
    expect(renderMarkdown('[pincha](javascript:alert(1))')).not.toContain('<a ')
    // …y el saneador lo quita también cuando viene como HTML embebido, que es el
    // camino que este cambio acaba de abrir.
    const html = renderMarkdown('<a href="javascript:alert(1)">pincha</a>')
    expect(html).toContain('pincha')
    expect(html).not.toContain('javascript:')
  })

  it('desactiva las URL data:', () => {
    const html = renderMarkdown('<img src="data:text/html,<script>alert(1)</script>">')
    expect(html).not.toContain('data:text/html')
  })

  it.each(['iframe', 'object', 'embed', 'form', 'style', 'template'])('quita <%s>', (tag) => {
    expect(renderMarkdown(`<${tag}>x</${tag}>`)).not.toContain(`<${tag}`)
  })

  it('deja pasar el HTML que solo significa, no ejecuta', () => {
    const html = renderMarkdown(
      '<details><summary>Más</summary>oculto</details> <abbr title="SIP">SIP</abbr> <kbd>Esc</kbd>',
    )
    expect(html).toContain('<details>')
    expect(html).toContain('<summary>')
    expect(html).toContain('<abbr title="SIP">')
    expect(html).toContain('<kbd>')
  })

  it('conserva los enlaces y las imágenes normales', () => {
    const html = renderMarkdown('[doc](/uploads/x.png) ![alt](https://example.test/a.png)')
    expect(html).toContain('href="/uploads/x.png"')
    expect(html).toContain('src="https://example.test/a.png"')
  })

  it('deja fuera cualquier input que no sea una casilla deshabilitada', () => {
    const html = renderMarkdown('<input type="text" value="robado">')
    expect(html).not.toContain('<input')
  })
})

describe('GFM: nada de lo que ya se pintaba se ha perdido', () => {
  it('pinta tablas con su alineación', () => {
    const html = renderMarkdown('| a | b |\n|:--|--:|\n| 1 | 2 |')
    expect(html).toContain('<table>')
    // La alineación llega como clase y no como `style`: el saneador quita los
    // estilos en línea, así que markdown.js la traduce antes de que se pierda.
    expect(html).toContain('class="align-left"')
    expect(html).toContain('class="align-right"')
    expect(html).not.toContain('style=')
  })

  it('pinta tachado', () => {
    expect(renderMarkdown('~~fuera~~')).toContain('<s>')
  })

  it('conserva la clase de lenguaje que busca el resaltador', () => {
    const html = renderMarkdown('```python\nprint(1)\n```')
    expect(html).toContain('class="language-python"')
  })

  it('deja el bloque mermaid intacto para que prose.js lo convierta', () => {
    expect(renderMarkdown('```mermaid\ngraph TD;\n```')).toContain('class="language-mermaid"')
  })

  it('no ejecuta el HTML que vive dentro de un bloque de código', () => {
    const html = renderMarkdown('```html\n<script>alert(1)</script>\n```')
    expect(html).not.toContain('<script>alert')
    expect(html).toContain('&lt;script&gt;')
  })
})

describe('GFM: lo que faltaba', () => {
  it('pinta listas de tareas', () => {
    const html = renderMarkdown('- [ ] pendiente\n- [x] hecha')
    expect(html).toContain('type="checkbox"')
    expect(html).toContain('checked')
    expect(html).not.toContain('[ ]')
  })

  it('deja las casillas deshabilitadas: la vista de lectura lee', () => {
    expect(renderMarkdown('- [x] hecha')).toContain('disabled')
  })

  it('marca las matemáticas en línea sin pintarlas todavía', () => {
    const html = renderMarkdown('la energía es $E = mc^2$ y ya')
    expect(html).toContain('<span class="math">E = mc^2</span>')
  })

  it('marca las matemáticas en bloque', () => {
    expect(renderMarkdown('$$\\int_0^1 x\\,dx$$')).toContain('class="math math--block"')
  })

  it('escapa el origen de la fórmula, que llega desde la página', () => {
    const html = renderMarkdown('$<script>alert(1)</script>$')
    expect(html).not.toContain('<script>alert')
  })

  it('no confunde los precios con fórmulas', () => {
    const html = renderMarkdown('cuesta $10 y no $20')
    expect(html).not.toContain('class="math"')
  })
})

describe('frontmatter', () => {
  it('no se pinta como encabezado', () => {
    const html = renderMarkdown('---\ntype: runbook\nowner: sre\n---\n\nEl cuerpo.')
    expect(html).not.toContain('type: runbook')
    expect(html).not.toContain('<h2>')
    expect(html).toContain('El cuerpo.')
  })

  it('solo se recorta al principio', () => {
    const html = renderMarkdown('Texto.\n\n---\n\nMás texto.')
    expect(html).toContain('Texto.')
    expect(html).toContain('Más texto.')
    expect(html).toContain('<hr>')
  })

  it('un documento sin frontmatter no cambia', () => {
    expect(renderMarkdown('# Hola\n\nQué tal.')).toContain('<h1>Hola</h1>')
  })
})
