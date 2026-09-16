// A draft lives in the writer's browser, not on the server. The editor's save button and
// unsaved-changes guard cover leaving, not the server leaving: if the Pi stops answering
// mid-paragraph, the text exists only in React state and a reload takes it.
//
// It deliberately does not autosave against the API: every server save is a git commit,
// and autosaving would turn a page's history into one commit per typing pause.
//
// The key carries workspace and slug, so two half-written pages do not collide.

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
