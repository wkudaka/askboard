import { describe, expect, it } from 'vitest'
import type { Panel } from '../../api/types'
import { integerAxis } from './chartUtils'

const panel = (formats: Panel['formats'], y: string[]): Panel => ({
  id: 'p1', type: 'bar', title: 't', sql: '', columns: [], rows: [], truncated: false,
  encoding: { x: 'x', y, series: null }, alternatives: [], formats,
})

describe('integerAxis', () => {
  it('is true when every plotted metric is an integer count', () => {
    expect(integerAxis(panel({ pedidos: 'integer' }, ['pedidos']))).toBe(true)
  })

  it('is false when any plotted metric has decimals', () => {
    expect(integerAxis(panel({ pedidos: 'integer', receita: 'currency' }, ['pedidos', 'receita']))).toBe(false)
    expect(integerAxis(panel({}, ['peso']))).toBe(false)
  })
})
