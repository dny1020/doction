import { stableIndex } from './avatar.js'

// Each workspace is a blueprint sheet in one of six fixed hues (DESIGN.md §2). The hue is
// derived from the slug, so a workspace keeps its colour on every device without storing it.
// Chroma is per hue: petrol and forest leave sRGB at the others' 0.085.
export const WORKSPACE_TONES = [
  { name: 'prussian', hue: 258, chroma: 0.085 },
  { name: 'petrol', hue: 215, chroma: 0.05 },
  { name: 'indigo', hue: 285, chroma: 0.085 },
  { name: 'plum', hue: 335, chroma: 0.085 },
  { name: 'forest', hue: 155, chroma: 0.065 },
  { name: 'tile', hue: 30, chroma: 0.085 },
]

export function workspaceTone(slug) {
  return WORKSPACE_TONES[stableIndex(slug, WORKSPACE_TONES.length)]
}

// Without a slug (login, register) the stylesheet's default, prussian, stays.
export function applyWorkspaceTone(slug) {
  const style = document.documentElement.style
  if (!slug) {
    style.removeProperty('--ws-h')
    style.removeProperty('--ws-c')
    return
  }
  const tone = workspaceTone(slug)
  style.setProperty('--ws-h', String(tone.hue))
  style.setProperty('--ws-c', String(tone.chroma))
}
