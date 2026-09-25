import { useEffect, useState } from 'react'

// A loading placeholder shaped like what is coming, shown only after a delay: one that
// flashes for 80 ms reads as a glitch.
const DELAY = 250

function useVisibleAfterDelay(delay = DELAY) {
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const timer = setTimeout(() => setVisible(true), delay)
    return () => clearTimeout(timer)
  }, [delay])
  return visible
}

// Sidebar tree: real row heights and indents, so nothing shifts when the tree arrives.
export function TreeSkeleton({ rows = 7 }) {
  const visible = useVisibleAfterDelay()
  if (!visible) return null
  // Fixed rather than random indents: a tree that dances on every load draws the eye
  // exactly when there is nothing to look at.
  const levels = [0, 0, 1, 1, 2, 0, 1]
  return (
    <div className="skeleton-tree" aria-hidden="true">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="skeleton-row" data-level={levels[i % levels.length]}>
          <span className="skeleton-bar" />
        </div>
      ))}
    </div>
  )
}

// Document body: a headline and paragraphs at the reading column's width.
export function DocumentSkeleton() {
  const visible = useVisibleAfterDelay()
  if (!visible) return null
  return (
    <div className="skeleton-doc" aria-hidden="true">
      <span className="skeleton-bar skeleton-bar--title" />
      <span className="skeleton-bar" />
      <span className="skeleton-bar" />
      <span className="skeleton-bar skeleton-bar--short" />
      <span className="skeleton-bar" />
      <span className="skeleton-bar skeleton-bar--short" />
    </div>
  )
}

// List rows, for the trash, the inbox and settings.
export function ListSkeleton({ rows = 4 }) {
  const visible = useVisibleAfterDelay()
  if (!visible) return null
  return (
    <div className="skeleton-list" aria-hidden="true">
      {Array.from({ length: rows }, (_, i) => (
        <span key={i} className="skeleton-bar" />
      ))}
    </div>
  )
}
