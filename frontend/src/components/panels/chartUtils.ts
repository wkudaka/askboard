import type { CellValue, Panel, ValueFormat } from '../../api/types'
import { formatValue, type FormatOptions } from '../../lib/format'

/** Categorical slots in fixed order (validated palette, see index.css). Never cycled. */
export const MAX_SERIES = 8

export function seriesColor(index: number): string {
  return `var(--series-${Math.min(index, MAX_SERIES - 1) + 1})`
}

export interface PanelProps {
  panel: Panel
  format: FormatOptions
}

export function valueFormatter(panel: Panel, format: FormatOptions) {
  // With a pivoted series every plotted key shares the single y column's format.
  const shared: ValueFormat | undefined = panel.encoding.series ? panel.formats[panel.encoding.y[0]] : undefined
  return (key: string, value: CellValue) => formatValue(value, shared ?? panel.formats[key], format)
}

export const AXIS_TICK = { fill: 'var(--text)', fontSize: 12 }
export const GRID_STROKE = 'var(--chart-grid)'

/** Counts get whole-number ticks (no "0.5 orders"). */
export function integerAxis(panel: Panel): boolean {
  const { y, series } = panel.encoding
  const keys = series ? y.slice(0, 1) : y
  return keys.length > 0 && keys.every((key) => panel.formats[key] === 'integer')
}
