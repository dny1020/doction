import { useEffect } from 'react'

// The tab title, ordered specific to general — page, workspace, application — which is
// the order that survives a tab being truncated: what shows first is what tells two of
// them apart.
const APP = 'doction'

export function useDocumentTitle(page, workspace) {
  useEffect(() => {
    const parts = [page, workspace].filter(Boolean)
    // `document.title` is text by definition, so a title with HTML-significant
    // characters comes out literal.
    document.title = parts.length > 0 ? parts.join(' | ') + ' — ' + APP : APP
    return () => {
      document.title = APP
    }
  }, [page, workspace])
}
