import { forwardRef, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { renderMarkdown } from '../markdown.js'
import { enhanceProse } from '../prose.js'
import { APP_BASE } from '../config.js'

// Renders sanitized markdown into .prose, then enhances it. The ref reaches the .prose div
// so the Reader builds its TOC from painted headings. `ws` and `slugs` resolve wikilinks.
const Markdown = forwardRef(function Markdown({ text, ws, slugs }, ref) {
  const navigate = useNavigate()

  useEffect(() => {
    enhanceProse(ref.current)
  }, [text, ref])

  // A wikilink is an <a href> inside the document's HTML, not a <Link>, so on its own it
  // reloads the whole app. Plain clicks are intercepted and routed client-side; the ones
  // asking to open another way (middle click, new tab, save) pass through.
  function onClick(event) {
    const link = event.target.closest?.('a.wikilink')
    if (!link) return
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return
    }
    const href = link.getAttribute('href')
    if (!href || !href.startsWith(APP_BASE + '/')) return
    event.preventDefault()
    navigate(href.slice(APP_BASE.length))
  }

  const html = useMemo(() => renderMarkdown(text, { ws, slugs }), [text, ws, slugs])
  return (
    <div ref={ref} className="prose" onClick={onClick} dangerouslySetInnerHTML={{ __html: html }} />
  )
})

export default Markdown
