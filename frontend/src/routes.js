// Every content route hangs off the workspace: /w/<ws>/…. Built here so no link is left
// on the old scheme — one would be enough to open another workspace's page.
//
// Pages sit under /w/<ws>/p/<slug> and not /w/<ws>/<slug> on purpose: the slug is chosen
// by the writer, and a page titled "new", "trash" or "notes" would shadow those routes.

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
