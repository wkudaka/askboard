import { describe, expect, it } from 'vitest'
import { groupByDate } from './dates'

const now = new Date(2026, 10, 20, 15, 0) // 20 Nov 2026, local time
const at = (y: number, m: number, d: number, h = 12) => ({ id: `${y}-${m}-${d}`, when: new Date(y, m, d, h).toISOString() })

describe('groupByDate', () => {
  it('buckets items like a chat sidebar, keeping their order', () => {
    const items = [
      at(2026, 10, 20, 1),
      at(2026, 10, 19, 23),
      at(2026, 10, 15),
      at(2026, 10, 1),
      at(2026, 7, 3),
      at(2025, 11, 31),
    ]

    const groups = groupByDate(items, (i) => i.when, now)

    expect(groups.map((g) => [g.label, g.items.length])).toEqual([
      ['Today', 1],
      ['Yesterday', 1],
      ['Previous 7 days', 1],
      ['Previous 30 days', 1],
      ['August', 1],
      ['2025', 1],
    ])
  })

  it('returns no groups for no items', () => {
    expect(groupByDate([], () => '', now)).toEqual([])
  })
})
