// Every content route hangs off /w/<ws>/. Pages live under /p/<slug> so a page titled
// "new" or "trash" cannot shadow a route.

export function wsPath(ws, rest = '') {
  return '/w/' + ws + rest
}

export function pagePath(ws, slug, suffix = '') {
  return wsPath(ws, '/p/' + slug + suffix)
}

export function newPagePath(ws, parentSlug) {
  return wsPath(ws, parentSlug ? '/new?parent=' + parentSlug : '/new')
}

// A wikilink to a page that does not exist yet leads to writing it, with the target
// pre-filled as the title; the server derives the slug from that.
export function newPageWithTitlePath(ws, title) {
  return wsPath(ws, '/new?title=' + encodeURIComponent(title))
}
