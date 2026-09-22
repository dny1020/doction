import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useOutletContext } from 'react-router-dom'
import {
  LABEL_AT,
  LABEL_BASELINE,
  NODE_R,
  buildSimulation,
  labelOf,
  radius,
} from '../graphLayout.js'
import { api, isAbort } from '../api.js'
import { useI18n } from '../i18n.jsx'
import { pagePath } from '../routes.js'
import EmptyState from '../components/EmptyState.jsx'
import { ListSkeleton } from '../components/Skeleton.jsx'
import { useDocumentTitle } from '../useDocumentTitle.js'

// The bird's-eye view: the workspace as its wikilink graph.
//
// Drawn as SVG the application writes itself rather than letting a library render. d3-force
// only solves positions here — it is a numerical solver, not a renderer — so every colour
// and face comes from the theme variables through ordinary CSS and dark mode needs no
// bridge. That is the lesson from mermaid, which did need its palette carried by hand.

function reducedMotion() {
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  } catch {
    return false
  }
}

export default function Graph() {
  const { ws } = useOutletContext()
  const { t } = useI18n()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [error, setError] = useState(false)
  // The counter is never read: it exists so the simulation can request a repaint without
  // putting positions into state.
  const [, setTick] = useState(0)
  const [hover, setHover] = useState(null)
  const [view, setView] = useState({ x: 0, y: 0, k: 1 })
  // World origin is (0,0) because that is where `forceCenter` pulls, but in an SVG (0,0)
  // is the corner: without measuring the canvas the graph draws against the edge.
  const [size, setSize] = useState({ w: 0, h: 0 })

  const svgRef = useRef(null)
  const simRef = useRef(null)
  const nodesRef = useRef([])
  const linksRef = useRef([])
  const dragRef = useRef(null)
  const panRef = useRef(null)
  const movedRef = useRef(null)

  useDocumentTitle(t('graph'), ws)

  // ResizeObserver rather than window.resize: the sidebar collapses and the canvas
  // changes width without the window noticing.
  //
  // It depends on `data` because the <svg> does not exist until there is a graph, and it
  // only writes state when the measurement actually changed: a new object per notification
  // would cause a render, and that render another notification.
  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return undefined
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      setSize((prev) => (prev.w === width && prev.h === height ? prev : { w: width, h: height }))
    })
    observer.observe(svg)
    return () => observer.disconnect()
  }, [data])

  useEffect(() => {
    const controller = new AbortController()
    setData(null)
    setError(false)
    api
      .get('/api/graph', controller.signal)
      .then(setData)
      .catch((e) => {
        if (!isAbort(e)) setError(true)
      })
    return () => controller.abort()
  }, [ws])

  // The simulation lives outside React: mutating positions in state every frame would
  // repaint the whole tree sixty times a second. This only signals a redraw, and the SVG
  // reads the positions by reference.
  useEffect(() => {
    if (!data || data.nodes.length === 0) return undefined

    const nodes = data.nodes.map((n) => ({ ...n }))
    const byId = new Map(nodes.map((n) => [n.slug, n]))
    // A broken target is not a page, so it gets a ghost node: the edge has somewhere to
    // end, and it is visible that it ends in nothing.
    for (const e of data.edges) {
      if (e.broken && !byId.has(e.target)) {
        const ghost = { slug: e.target, title: e.target, broken: true, incoming: 0, outgoing: 0 }
        byId.set(e.target, ghost)
        nodes.push(ghost)
      }
    }
    const links = data.edges
      .filter((e) => byId.has(e.source) && byId.has(e.target))
      .map((e) => ({ ...e }))

    nodesRef.current = nodes
    linksRef.current = links

    const sim = buildSimulation(nodes, links)

    simRef.current = sim

    // With reduced motion the entrance is not animated: the layout is solved in full
    // before the first paint and drawn already still.
    if (reducedMotion()) {
      sim.tick(300)
      setTick((n) => n + 1)
      return () => sim.stop()
    }
    sim.on('tick', () => setTick((n) => n + 1))
    sim.alpha(1).restart()
    return () => {
      sim.on('tick', null)
      sim.stop()
    }
  }, [data])

  // ── Drag and pan ───────────────────────────────────────────────────────────

  const toWorld = useCallback(
    (event) => {
      const rect = svgRef.current.getBoundingClientRect()
      return {
        x: (event.clientX - rect.left - rect.width / 2) / view.k - view.x,
        y: (event.clientY - rect.top - rect.height / 2) / view.k - view.y,
      }
    },
    [view],
  )

  // screen = centre + k * (world + pan). `toWorld` is the inverse.
  const worldTransform = `translate(${size.w / 2}, ${size.h / 2}) scale(${view.k}) translate(${view.x}, ${view.y})`

  const onPointerDown = (event, node) => {
    event.currentTarget.setPointerCapture(event.pointerId)
    if (node) {
      dragRef.current = node
      // A drag ends in the same `click` a tap does, so without this moving a node opened
      // its page. Record where it started and how far it moved.
      movedRef.current = { x: event.clientX, y: event.clientY, moved: false }
      simRef.current?.alphaTarget(0.2).restart()
    } else {
      panRef.current = { px: event.clientX, py: event.clientY, ...view }
    }
  }

  const onPointerMove = (event) => {
    if (dragRef.current) {
      const from = movedRef.current
      if (from && Math.hypot(event.clientX - from.x, event.clientY - from.y) > 4) {
        from.moved = true
      }
      const p = toWorld(event)
      dragRef.current.fx = p.x
      dragRef.current.fy = p.y
      setTick((n) => n + 1)
    } else if (panRef.current) {
      const start = panRef.current
      const dx = (event.clientX - start.px) / start.k
      const dy = (event.clientY - start.py) / start.k
      setView((v) => ({ ...v, x: start.x + dx, y: start.y + dy }))
    }
  }

  const onPointerUp = () => {
    if (dragRef.current) {
      // Release the pin, so the node obeys the forces again and the graph settles back
      // instead of staying deformed.
      dragRef.current.fx = null
      dragRef.current.fy = null
      dragRef.current = null
      simRef.current?.alphaTarget(0)
    }
    panRef.current = null
  }

  const onWheel = (event) => {
    const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12
    setView((v) => ({ ...v, k: Math.min(4, Math.max(0.25, v.k * factor)) }))
  }

  const counts = useMemo(() => {
    if (!data) return null
    return {
      nodes: data.nodes.length,
      edges: data.edges.length,
      orphans: data.nodes.filter((n) => n.orphan).length,
      broken: data.edges.filter((e) => e.broken).length,
    }
  }, [data])

  if (error) {
    return (
      <div className="settings">
        <h1 className="settings-h1">{t('graph')}</h1>
        <EmptyState title={t('graph_empty')} hint={t('graph_empty_desc')} />
      </div>
    )
  }
  if (!data) return <ListSkeleton rows={6} />
  if (data.nodes.length === 0) {
    return (
      <div className="settings">
        <h1 className="settings-h1">{t('graph')}</h1>
        <EmptyState title={t('graph_empty')} hint={t('graph_empty_desc')} />
      </div>
    )
  }

  const nodes = nodesRef.current
  const links = linksRef.current
  const labelAll = nodes.length <= LABEL_AT

  return (
    <div className="graph-page">
      <header className="graph-header">
        <h1 className="settings-h1">{t('graph')}</h1>
        <p className="card-desc">{t('graph_desc')}</p>
        <dl className="graph-facts">
          <Fact value={counts.nodes} label={t('graph_nodes')} />
          <Fact value={counts.edges} label={t('graph_edges')} />
          <Fact value={counts.orphans} label={t('graph_orphans')} />
          <Fact value={counts.broken} label={t('graph_broken')} tone="danger" />
        </dl>
        {data.truncated && (
          <p className="graph-note">
            {t('graph_truncated').replace('{n}', counts.nodes).replace('{total}', data.pages)}
          </p>
        )}
      </header>

      <svg
        ref={svgRef}
        className="card graph-canvas"
        role="img"
        aria-label={t('graph_desc')}
        onPointerDown={(e) => onPointerDown(e, null)}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
        onWheel={onWheel}
      >
        <g transform={worldTransform} className="graph-world">
          {links.map((l, i) => (
            <line
              key={i}
              className={l.broken ? 'graph-edge graph-edge--broken' : 'graph-edge'}
              x1={l.source.x}
              y1={l.source.y}
              x2={l.target.x}
              y2={l.target.y}
            />
          ))}
          {nodes.map((n) => (
            <g
              key={n.slug}
              className={
                'graph-node' +
                (n.broken ? ' graph-node--broken' : '') +
                (n.orphan ? ' graph-node--orphan' : '') +
                (hover === n.slug ? ' is-hover' : '')
              }
              transform={`translate(${n.x || 0}, ${n.y || 0})`}
              onPointerDown={(e) => {
                e.stopPropagation()
                onPointerDown(e, n)
              }}
              onPointerEnter={() => setHover(n.slug)}
              onPointerLeave={() => setHover(null)}
              onClick={() => {
                if (movedRef.current?.moved || n.broken) return
                navigate(pagePath(ws, n.slug))
              }}
            >
              <circle r={n.broken ? NODE_R : radius(n)} />
              {(labelAll || n.incoming > 0 || hover === n.slug) && (
                <text y={radius(n) + LABEL_BASELINE}>{labelOf(n.title)}</text>
              )}
            </g>
          ))}
        </g>
      </svg>
    </div>
  )
}

function Fact({ value, label, tone }) {
  return (
    <div className={tone === 'danger' && value > 0 ? 'graph-fact graph-fact--alert' : 'graph-fact'}>
      <dt className="graph-fact-value">{value}</dt>
      <dd className="graph-fact-label">{label}</dd>
    </div>
  )
}
