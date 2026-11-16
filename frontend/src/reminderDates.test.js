import { describe, expect, it } from 'vitest'
import { localDateTime, reminderDate } from './reminderDates.js'
import { setWorkspace, withWorkspace } from './api.js'

describe('reminder calendar dates and instants', () => {
  it('keeps date-only reminders on their calendar day', () => {
    expect(reminderDate({ due_date: '2026-11-17', timezone: 'Pacific/Honolulu' }, 'en-US')).toBe(
      'Nov 17, 2026',
    )
  })
  it('edits a stored UTC instant in the reminder timezone', () => {
    expect(localDateTime('2026-11-17T14:00:00Z', 'America/Bogota')).toBe('2026-11-17T09:00')
    expect(localDateTime('2026-11-17T01:00:00Z', 'America/Bogota')).toBe('2026-11-16T20:00')
  })
  it('preserves an explicit workspace when selecting linked documents', () => {
    setWorkspace('personal')
    expect(withWorkspace('/api/pages?ws=work')).toBe('/api/pages?ws=work')
    expect(withWorkspace('/api/pages')).toBe('/api/pages?ws=personal')
    setWorkspace(null)
  })
})
