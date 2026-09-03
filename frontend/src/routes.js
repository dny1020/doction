// Toda ruta de contenido cuelga del workspace: /w/<ws>/…. Se construyen aquí para
// que no quede ningún enlace en el esquema viejo — uno solo bastaría para abrir
// la página de otro workspace.
//
// Las páginas van bajo /w/<ws>/p/<slug> y no bajo /w/<ws>/<slug> a propósito: el
// slug lo elige quien escribe, y una página titulada "new", "trash" o "notes"
// taparía esas rutas sin que nadie lo notara.

export function wsPath(ws, rest = '') {
  return '/w/' + ws + rest
}

export function pagePath(ws, slug, suffix = '') {
  return wsPath(ws, '/p/' + slug + suffix)
}

export function newPagePath(ws, parentSlug) {
  return wsPath(ws, parentSlug ? '/new?parent=' + parentSlug : '/new')
}
