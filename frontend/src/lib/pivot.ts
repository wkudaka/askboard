import type { CellValue, Panel } from '../api/types'

export const BLANK = '(blank)'

export type ChartRecord = Record<string, CellValue>

export interface ChartData {
  data: ChartRecord[]
  /** Keys plotted as series: the y columns, or the pivoted series values. */
  series: string[]
}

function label(value: CellValue): string {
  if (value === null || value === undefined || value === '') return BLANK
  if (typeof value === 'boolean') return value ? 'yes' : 'no'
  return String(value)
}

/** Turns a panel's rows into Recharts records, pivoting `encoding.series` into columns. */
export function toChartData(panel: Panel): ChartData {
  const index = new Map(panel.columns.map((c, i) => [c.name, i]))
  const { x, y, series } = panel.encoding
  const xIndex = x ? index.get(x) : undefined
  const xType = x ? panel.columns[index.get(x) ?? -1]?.type : undefined
  const xValue = (row: CellValue[]): CellValue => {
    if (xIndex === undefined) return null
    const v = row[xIndex]
    return xType === 'number' && v !== null ? v : label(v)
  }

  if (!series) {
    const data = panel.rows.map((row) => {
      const record: ChartRecord = {}
      if (x) record[x] = xValue(row)
      for (const name of y) record[name] = row[index.get(name) ?? -1] ?? null
      return record
    })
    return { data, series: [...y] }
  }

  const seriesIndex = index.get(series) ?? -1
  const yIndex = index.get(y[0]) ?? -1
  const byX = new Map<string, ChartRecord>()
  const seriesNames: string[] = []
  for (const row of panel.rows) {
    const xv = xValue(row)
    const key = String(xv)
    const name = label(row[seriesIndex])
    if (!seriesNames.includes(name)) seriesNames.push(name)
    let record = byX.get(key)
    if (!record) {
      record = x ? { [x]: xv } : {}
      byX.set(key, record)
    }
    record[name] = row[yIndex] ?? null
  }
  return { data: [...byX.values()], series: seriesNames }
}
