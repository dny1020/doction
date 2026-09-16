import { describe, expect, it } from 'vitest'
import { LABEL_BASELINE, buildSimulation, halfLabel, labelOf, radius } from './graphLayout.js'

// The graph view's defect was a layout one: nodes collapsed into the centre, labels on top of
// each other, most of the canvas empty. That is measurable, so it is measured here rather than
// looked at — the simulation is deterministic once it has settled, so these do not flake.

const CANVAS = { w: 900, h: 560 }

function workspace(n, { titleLength = 14, chain = true } = {}) {
  const nodes = Array.from({ length: n }, (_, i) => ({
    slug: `page-${i}`,
    title: `Page ${i} `.padEnd(titleLength, 'x'),
    incoming: 0,
    outgoing: 0,
  }))
  const links = []
  if (chain) {
    for (let i = 1; i < n; i += 1) {
      links.push({ source: `page-${i - 1}`, target: `page-${i}` })
      nodes[i].incoming += 1
      nodes[i - 1].outgoing += 1
    }
  }
  return { nodes, links }
}

function settle(nodes, links) {
  const sim = buildSimulation(nodes, links)
  sim.tick(400)
  return nodes
}

// The box a node actually occupies on screen: the circle, and the label centred beneath it.
function boxOf(node) {
  const half = Math.max(radius(node), halfLabel(node))
  return {
    x0: node.x - half,
    x1: node.x + half,
    y0: node.y - radius(node),
    y1: node.y + LABEL_BASELINE + 4,
  }
}

function overlaps(a, b) {
  return a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1
}

function overlappingPairs(nodes) {
  const boxes = nodes.map(boxOf)
  const hits = []
  for (let i = 0; i < boxes.length; i += 1) {
    for (let j = i + 1; j < boxes.length; j += 1) {
      if (overlaps(boxes[i], boxes[j])) hits.push([nodes[i].slug, nodes[j].slug])
    }
  }
  return hits
}

function extent(nodes) {
  const xs = nodes.map((n) => n.x)
  const ys = nodes.map((n) => n.y)
  return { w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys) }
}

describe('the layout separates what it draws', () => {
  it('leaves no two labels on top of each other in a small workspace', () => {
    // The size the issue named: at fifteen pages the labels were already illegible.
    const { nodes, links } = workspace(15)
    settle(nodes, links)
    expect(overlappingPairs(nodes)).toEqual([])
  })

  it('separates long titles too, because a node is as wide as its name', () => {
    const { nodes, links } = workspace(15, { titleLength: 24 })
    settle(nodes, links)
    expect(overlappingPairs(nodes)).toEqual([])
  })

  it('separates a workspace with no links at all', () => {
    // Orphans feel only the repulsion and the weak pull to the centre.
    const { nodes, links } = workspace(12, { chain: false })
    settle(nodes, links)
    expect(overlappingPairs(nodes)).toEqual([])
  })
})

describe('the layout uses the canvas it is given', () => {
  it('spreads a small workspace across a useful part of it', () => {
    const { nodes, links } = workspace(15)
    settle(nodes, links)
    const { w } = extent(nodes)
    // The complaint was a clump in the middle of an empty canvas.
    expect(w).toBeGreaterThan(CANVAS.w * 0.4)
  })

  it('spends its space sideways, matching a landscape canvas', () => {
    const { nodes, links } = workspace(20)
    settle(nodes, links)
    const { w, h } = extent(nodes)
    expect(w).toBeGreaterThan(h)
  })

  it('does not fly apart at the node limit', () => {
    // distanceMax is what keeps the strong repulsion bounded here.
    const { nodes, links } = workspace(300)
    settle(nodes, links)
    const { w, h } = extent(nodes)
    expect(w).toBeLessThan(CANVAS.w * 12)
    expect(h).toBeLessThan(CANVAS.h * 12)
    expect(nodes.every((n) => Number.isFinite(n.x) && Number.isFinite(n.y))).toBe(true)
  })
})

describe('labels are bounded', () => {
  it('elides a title too long to draw', () => {
    const long = 'A runbook title far longer than the graph can show'
    expect(labelOf(long).length).toBeLessThanOrEqual(24)
    expect(labelOf(long).endsWith('…')).toBe(true)
  })

  it('leaves a short title alone', () => {
    expect(labelOf('Kamailio')).toBe('Kamailio')
  })

  it('survives a page with no title', () => {
    expect(labelOf(undefined)).toBe('')
    expect(halfLabel({ title: undefined })).toBe(0)
  })
})
