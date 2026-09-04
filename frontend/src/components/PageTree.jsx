import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { useI18n } from '../i18n.jsx'
import { pagePath } from '../routes.js'
import PageActions from './PageActions.jsx'

// Árbol de páginas de la barra lateral. Antes era una lista plana con `data-depth`:
// la jerarquía se veía como sangrado y nada más, así que un workspace grande era un
// scroll de cien filas sin forma de plegar nada ni de recorrerlo con el teclado.
//
// La API sigue devolviendo la lista plana en orden DFS con `depth` — es suficiente
// para reconstruir el árbol aquí y no hace falta tocar el backend.
//
// Se guarda lo plegado y no lo desplegado a propósito: así el estado inicial es el
// árbol entero abierto, que es exactamente lo que se veía antes de este cambio.

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

// Filas visibles, en orden de pantalla: lo que hay dentro de una rama plegada no
// existe para el teclado, igual que no existe para el ratón.
function flatten(nodes, collapsed, level, out) {
  for (const node of nodes) {
    out.push({ node, level })
    if (node.children.length > 0 && !collapsed.has(node.slug)) {
      flatten(node.children, collapsed, level + 1, out)
    }
  }
  return out
}

// Los ancestros de una página, para poder revelarla al abrirla.
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

  // Abrir una página revela su rama. Se hace al cambiar de página y no en cada
  // render para que plegar la rama en la que estás siga funcionando.
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

  // El foco se recuerda por slug y no por posición: si el árbol se recarga tras
  // crear, mover, renombrar o borrar, la fila sigue siendo la misma y el foco no
  // vuelve al principio de la lista.
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
    // El foco se queda en la rama que se acaba de plegar o desplegar. Sin esto,
    // plegar una rama con el foco dentro dejaba el foco en una fila que ya no
    // existe, y volvía al principio del árbol.
    setFocusSlug(slug)
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (open) next.delete(slug)
      else next.add(slug)
      return next
    })
  }

  // Un único punto de tabulación para todo el árbol (roving tabindex): dentro se
  // mueve uno con las flechas, y Enter lo abre — el enlace ya lo hace solo, así
  // que Enter no se intercepta.
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
        // Sin rama que plegar, izquierda sube al padre: la fila anterior con un
        // nivel menos.
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
              // Fuera del orden de tabulación y del árbol de accesibilidad: el
              // estado ya lo dice aria-expanded de la fila y las flechas ya lo
              // cambian. Aquí es solo el afordance de ratón y de dedo.
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
