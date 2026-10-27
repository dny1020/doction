import { describe, expect, it } from 'vitest'
import { WORKSPACE_TONES, workspaceTone } from './workspaceTone.js'

describe('workspaceTone', () => {
  it('gives a workspace the same tone every time', () => {
    expect(workspaceTone('infra')).toBe(workspaceTone('infra'))
  })

  it('always lands on one of the six tones, empty slug included', () => {
    for (const slug of ['', 'personal', 'clientes', 'lab', 'a-very-long-workspace-slug']) {
      expect(WORKSPACE_TONES).toContain(workspaceTone(slug))
    }
  })

  it('spreads common slugs over more than one tone', () => {
    const slugs = ['personal', 'infra', 'clientes', 'lab', 'homelab', 'telefonia']
    expect(new Set(slugs.map((s) => workspaceTone(s).name)).size).toBeGreaterThan(1)
  })
})
