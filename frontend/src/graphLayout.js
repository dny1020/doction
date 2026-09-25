import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY } from 'd3-force'

// Where the graph's nodes go, nothing about how they look. Separate from Graph.jsx so
// graphLayout.test.js can measure overlaps without a browser.

export const NODE_R = 5
export const MAX_R = 14
export const LABEL_AT = 40 // above this, only nodes with links are labelled

// Label geometry, shared by the collider and the renderer. Centred under the node, so each
// node is a symmetric box, the only shape forceCollide can model.
export const LABEL_PX = 6.6 // mean advance of the UI face at --text-sm (12px)
export const LABEL_BASELINE = 13 // from the node's centre down to the label's baseline
export const LABEL_MAX = 24 // characters; a title longer than this is elided

export function labelOf(title) {
  const text = title || ''
  return text.length > LABEL_MAX ? text.slice(0, LABEL_MAX - 1) + '…' : text
}

export function halfLabel(node) {
  return (labelOf(node.title).length * LABEL_PX) / 2
}

// A page's weight in the graph is how many pages point at it. Here rather than in the view
// because the collider sizes itself with this and the renderer draws the same circle.
export function radius(node) {
  return Math.min(MAX_R, NODE_R + Math.sqrt(node.incoming || 0) * 2.5)
}

// Every distance below is in label widths rather than in pixels chosen by eye. A node is as
// wide as its name, so a workspace of long titles needs more room than one of short ones,
// and the simulation is the only place that knows which it has.
export function buildSimulation(nodes, links) {
  return (
    forceSimulation(nodes)
      .force(
        'link',
        forceLink(links)
          .id((d) => d.slug)
          // Far enough apart that neither end's label reaches the other's node, plus a gap.
          // At a flat 70 a link was shorter than the two labels hanging off it.
          .distance((d) => 40 + halfLabel(d.source) + halfLabel(d.target))
          .strength(0.25),
      )
      // distanceMax is what lets the repulsion be this strong: without it every node pushes
      // every other one, so the strength had to stay low enough not to tear a 300-node
      // workspace apart and was then far too low to separate fifteen.
      .force('charge', forceManyBody().strength(-520).distanceMax(520))
      // The collider works on the whole label box, not the circle, which is what stops two
      // names overlapping while their nodes sit politely apart.
      .force('collide', forceCollide((d) => Math.max(radius(d), halfLabel(d)) + 8).strength(0.85))
      // forceX/forceY, not forceCenter, which holds no node, so orphans drifted off the canvas.
      // Y pulls harder than X: the canvas is wide and labels are horizontal.
      .force('x', forceX(0).strength(0.04))
      .force('y', forceY(0).strength(0.08))
      .stop()
  )
}
