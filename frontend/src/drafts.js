// Drafts live in the browser, so a server that stops answering mid-paragraph loses
// nothing. No autosave to the API: every save is a git commit. Keyed by workspace and slug.

const PREFIX = 'doction:draft:'

function key(ws, slug) {
  return PREFIX + ws + ':' + (slug || 'new')
}

export function readDraft(ws, slug) {
  try {
    const raw = localStorage.getItem(key(ws, slug))
    return raw ? JSON.parse(raw) : null
  } catch {
    // Storage blocked (private window) or corrupt: no draft, which is the status quo.
    return null
  }
}

export function writeDraft(ws, slug, draft) {
  try {
    localStorage.setItem(key(ws, slug), JSON.stringify(draft))
  } catch {
    // Blocked or full. Editing continues without the safety net, which interrupts nobody.
  }
}

export function clearDraft(ws, slug) {
  try {
    localStorage.removeItem(key(ws, slug))
  } catch {
    // as above
  }
}
