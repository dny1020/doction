import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { useI18n } from '../i18n.jsx'
import { pagePath } from '../routes.js'
import PageActions from './PageActions.jsx'

// The sidebar's page tree. The API returns a flat DFS list with `depth`, which is enough
// to rebuild the tree here.
//
// What is stored is what is *collapsed*, not what is expanded, so the initial state is the
// whole tree open.

function buildTree(pages) {
  const roots = []
  const ancestors = []
  for (const page of pages) {
    const node = { ...page, children: [] }
    ancestors.length = page.depth
    const parent = ancestors[page.depth - 1]
    if (parent) parent.children.push(node)
    else roots.push(node)
    ancestors[page.depth] = node
  }
  return roots
}

// Visible rows in screen order: what is inside a collapsed branch does not exist for the
// keyboard any more than it does for the mouse.
function flatten(nodes, collapsed, level, out) {
  for (const node of nodes) {
    out.push({ node, level })
    if (node.children.length > 0 && !collapsed.has(node.slug)) {
      flatten(node.children, collapsed, level + 1, out)
    }
  }
  return out
}

// A page's ancestors, so opening it can reveal it.
function pathTo(nodes, slug, trail = []) {
  for (const node of nodes) {
    if (node.slug === slug) return trail
    const found = pathTo(node.children, slug, trail.concat(node.slug))
    if (found) return found
  }
  return null
}

export default function PageTree({ ws, pages, activeSlug, onReload }) {
  const { t } = useI18n()
  const [collapsed, setCollapsed] = useState(() => new Set())
  const [focusSlug, setFocusSlug] = useState(null)
  const rowRefs = useRef(new Map())

  const roots = useMemo(() => buildTree(pages), [pages])
  const rows = useMemo(() => flatten(roots, collapsed, 1, []), [roots, collapsed])

  // Opening a page reveals its branch — on page change, not every render, so collapsing
  // the branch you are in still works.
  useEffect(() => {
    if (!activeSlug) return
    const trail = pathTo(roots, activeSlug)
    if (!trail || trail.length === 0) return
    setCollapsed((prev) => {
      if (!trail.some((slug) => prev.has(slug))) return prev
      const next = new Set(prev)
      for (const slug of trail) next.delete(slug)
      return next
    })
  }, [activeSlug, roots])

  // Focus is remembered by slug, not position, so a reload after create/move/rename/delete
  // keeps it on the same row instead of sending it back to the top.
  const focusIndex = useMemo(() => {
    const wanted = focusSlug || activeSlug
    const found = rows.findIndex((row) => row.node.slug === wanted)
    return found >= 0 ? found : 0
  }, [rows, focusSlug, activeSlug])

  const focusRow = useCallback(
    (index) => {
      const row = rows[index]
      if (!row) return
      setFocusSlug(row.node.slug)
      rowRefs.current.get(row.node.slug)?.focus()
    },
    [rows],
  )

  function toggle(slug, open) {
    // Focus stays on the branch just toggled; otherwise collapsing a branch with focus
    // inside it left focus on a row that no longer exists.
    setFocusSlug(slug)
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (open) next.delete(slug)
      else next.add(slug)
      return next
    })
  }

  // One tab stop for the whole tree (roving tabindex): arrows move inside it and Enter
  // opens — the link already does that, so Enter is not intercepted.
  function onKeyDown(event) {
    const row = rows[focusIndex]
    if (!row) return
    const open = row.node.children.length > 0 && !collapsed.has(row.node.slug)
    const hasChildren = row.node.children.length > 0

    if (event.key === 'ArrowDown') {
      focusRow(Math.min(focusIndex + 1, rows.length - 1))
    } else if (event.key === 'ArrowUp') {
      focusRow(Math.max(focusIndex - 1, 0))
    } else if (event.key === 'ArrowRight') {
      if (hasChildren && !open) toggle(row.node.slug, true)
      else if (hasChildren) focusRow(focusIndex + 1)
      else return
    } else if (event.key === 'ArrowLeft') {
      if (open) toggle(row.node.slug, false)
      else {
        // With no branch to collapse, left goes up to the parent.
        for (let i = focusIndex - 1; i >= 0; i--) {
          if (rows[i].level < row.level) {
            focusRow(i)
            break
          }
        }
      }
    } else if (event.key === 'Home') {
      focusRow(0)
    } else if (event.key === 'End') {
      focusRow(rows.length - 1)
    } else {
      return
    }
    event.preventDefault()
  }

  return (
    <ul role="tree" aria-label={t('pages')} onKeyDown={onKeyDown}>
      {rows.map((row, index) => {
        const { node, level } = row
        const hasChildren = node.children.length > 0
        const open = hasChildren && !collapsed.has(node.slug)
        const focused = index === focusIndex
        return (
          <li key={node.slug} className="page-row" role="none">
            <button
              className={'page-row-twisty' + (open ? ' open' : '')}
              type="button"
              // Out of the tab order and the accessibility tree: the row's aria-expanded
              // already says the state and the arrows already change it. This is only the
              // mouse and touch affordance.
              tabIndex={-1}
              aria-hidden="true"
              title={t('toggle_subpages')}
              disabled={!hasChildren}
              onClick={() => toggle(node.slug, !open)}
            >
              {hasChildren && <ChevronRight size={14} />}
            </button>
            <Link
              ref={(el) => {
                if (el) rowRefs.current.set(node.slug, el)
                else rowRefs.current.delete(node.slug)
              }}
              to={pagePath(ws, node.slug)}
              role="treeitem"
              aria-level={level}
              aria-selected={node.slug === activeSlug}
              aria-expanded={hasChildren ? open : undefined}
              tabIndex={focused ? 0 : -1}
              className={node.slug === activeSlug ? 'active' : undefined}
              onFocus={() => setFocusSlug(node.slug)}
            >
              {node.title}
            </Link>
            <PageActions page={node} pages={pages} onDone={onReload} tabIndex={focused ? 0 : -1} />
          </li>
        )
      })}
    </ul>
  )
}
