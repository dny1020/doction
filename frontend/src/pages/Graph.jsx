import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useOutletContext } from 'react-router-dom'
import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY } from 'd3-force'
import { api, isAbort } from '../api.js'
import { useI18n } from '../i18n.jsx'
import { pagePath } from '../routes.js'
import EmptyState from '../components/EmptyState.jsx'
import { ListSkeleton } from '../components/Skeleton.jsx'
import { useDocumentTitle } from '../useDocumentTitle.js'

// La vista de pájaro: el workspace como grafo de wikilinks.
//
// Se dibuja en SVG que escribe la propia aplicación en vez de dejar el render a
// la librería. d3-force aquí solo resuelve posiciones —es un solucionador
// numérico, no un renderizador—, así que cada color y cada tipo salen de las
// variables del tema por CSS normal y el modo oscuro no necesita puente alguno.
// Es la lección de mermaid, que sí tuvo que llevar su paleta a mano.

const NODE_R = 5
const MAX_R = 14
const LABEL_AT = 40 // por encima de esto solo se etiquetan los nodos con enlaces

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
  // El contador no se lee: existe para que la simulación pueda pedir un repintado
  // sin meter las posiciones en el estado, que es lo que haría lento el dibujo.
  const [, setTick] = useState(0)
  const [hover, setHover] = useState(null)
  const [view, setView] = useState({ x: 0, y: 0, k: 1 })
  // El origen del mundo es (0,0) porque ahí tira `forceCenter`, pero en un SVG
  // (0,0) es la esquina. Sin medir el lienzo el grafo se dibuja pegado al borde.
  const [size, setSize] = useState({ w: 0, h: 0 })

  const svgRef = useRef(null)
  const simRef = useRef(null)
  const nodesRef = useRef([])
  const linksRef = useRef([])
  const dragRef = useRef(null)
  const panRef = useRef(null)
  const movedRef = useRef(null)

  useDocumentTitle(t('graph'), ws)

  // Se mide con ResizeObserver y no con window.resize: la barra lateral se pliega
  // y el lienzo cambia de ancho sin que la ventana se entere.
  //
  // Depende de `data` porque el <svg> no existe hasta que hay grafo que dibujar, y
  // solo escribe el estado cuando la medida cambia de verdad: un objeto nuevo en
  // cada notificación provocaría un render, y ese render, otra notificación.
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

  // La simulación vive fuera de React: mutar posiciones en el estado en cada
  // fotograma repintaría el árbol entero sesenta veces por segundo. Aquí solo se
  // avisa de que hay que redibujar, y el SVG lee las posiciones por referencia.
  useEffect(() => {
    if (!data || data.nodes.length === 0) return undefined

    const nodes = data.nodes.map((n) => ({ ...n }))
    const byId = new Map(nodes.map((n) => [n.slug, n]))
    // Un destino roto no es una página: se le da un nodo fantasma para que la
    // arista tenga dónde terminar y se vea que termina en nada.
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

    const sim = forceSimulation(nodes)
      .force(
        'link',
        forceLink(links)
          .id((d) => d.slug)
          .distance(70)
          .strength(0.35),
      )
      .force('charge', forceManyBody().strength(-180))
      .force('collide', forceCollide(MAX_R + 6))
      // forceX/forceY en vez de forceCenter: el centrado solo desplaza el conjunto
      // y no sujeta a nadie, así que una página huérfana —sin aristas que tiren de
      // ella— salía disparada por la repulsión y acababa fuera del lienzo. Esto la
      // ata al centro con una fuerza floja, suficiente para que se quede a la vista
      // sin apelotonar el grupo conectado.
      .force('x', forceX(0).strength(0.06))
      .force('y', forceY(0).strength(0.06))
      .stop()

    simRef.current = sim

    // Con movimiento reducido no se anima la entrada: se resuelve el layout
    // entero antes del primer pintado y se dibuja ya quieto.
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

  // ── arrastre y desplazamiento ──────────────────────────────────────────────

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

  // pantalla = centro + k · (mundo + desplazamiento). El inverso es `toWorld`.
  const worldTransform = `translate(${size.w / 2}, ${size.h / 2}) scale(${view.k}) translate(${view.x}, ${view.y})`

  const onPointerDown = (event, node) => {
    event.currentTarget.setPointerCapture(event.pointerId)
    if (node) {
      dragRef.current = node
      // Un arrastre termina en el mismo `click` que un toque, así que sin esto
      // mover un nodo abría su página. Se anota dónde empezó y cuánto se movió.
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
      // Se suelta el anclaje: el nodo vuelve a obedecer a las fuerzas, que es lo
      // que hace que el grafo se reacomode en vez de quedar deformado.
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
  const radius = (n) => Math.min(MAX_R, NODE_R + Math.sqrt(n.incoming || 0) * 2.5)

  return (
    <div className="graph-page">
      <header className="graph-header">
        <h1 className="settings-h1">{t('graph')}</h1>
        <p className="settings-card-desc">{t('graph_desc')}</p>
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
        className="graph-canvas"
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
                <text x={radius(n) + 5} y="4">
                  {n.title}
                </text>
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
