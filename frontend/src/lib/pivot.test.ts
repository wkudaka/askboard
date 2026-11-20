import { describe, expect, it } from 'vitest'
import type { Panel } from '../api/types'
import { toChartData } from './pivot'

function panel(partial: Partial<Panel>): Panel {
  return {
    id: 'p1',
    type: 'bar',
    title: 't',
    sql: '',
    columns: [],
    rows: [],
    truncated: false,
    encoding: { x: null, y: [], series: null },
    alternatives: [],
    formats: {},
    ...partial,
  }
}

describe('toChartData', () => {
  it('maps rows to records keyed by column name', () => {
    const result = toChartData(
      panel({
        columns: [
          { name: 'cliente', type: 'text' },
          { name: 'pedidos', type: 'number' },
          { name: 'receita', type: 'number' },
        ],
        rows: [
          ['Ana', 3, 1341.71],
          ['Bruno', 1, 10],
        ],
        encoding: { x: 'cliente', y: ['pedidos', 'receita'], series: null },
      }),
    )

    expect(result.data).toEqual([
      { cliente: 'Ana', pedidos: 3, receita: 1341.71 },
      { cliente: 'Bruno', pedidos: 1, receita: 10 },
    ])
    expect(result.series).toEqual(['pedidos', 'receita'])
  })

  it('pivots a series column into one key per series, in first-seen order', () => {
    const result = toChartData(
      panel({
        columns: [
          { name: 'mes', type: 'date' },
          { name: 'cliente', type: 'text' },
          { name: 'receita', type: 'number' },
        ],
        rows: [
          ['2024-01-01', 'Bruno', 2],
          ['2024-01-01', 'Ana', 1],
          ['2024-02-01', 'Ana', 3],
          ['2024-02-01', null, 4],
        ],
        encoding: { x: 'mes', y: ['receita'], series: 'cliente' },
      }),
    )

    expect(result.series).toEqual(['Bruno', 'Ana', '(blank)'])
    expect(result.data).toEqual([
      { mes: '2024-01-01', Bruno: 2, Ana: 1 },
      { mes: '2024-02-01', Ana: 3, '(blank)': 4 },
    ])
  })

  it('labels missing categories', () => {
    const result = toChartData(
      panel({
        columns: [
          { name: 'cidade', type: 'text' },
          { name: 'n', type: 'number' },
        ],
        rows: [[null, 1]],
        encoding: { x: 'cidade', y: ['n'], series: null },
      }),
    )

    expect(result.data).toEqual([{ cidade: '(blank)', n: 1 }])
  })

  it('stringifies boolean categories', () => {
    const result = toChartData(
      panel({
        columns: [
          { name: 'pago', type: 'boolean' },
          { name: 'n', type: 'number' },
        ],
        rows: [
          [true, 3],
          [false, 2],
        ],
        encoding: { x: 'pago', y: ['n'], series: null },
      }),
    )

    expect(result.data.map((d) => d.pago)).toEqual(['yes', 'no'])
  })
})
