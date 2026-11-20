import type { CellValue } from '../../api/types'

export function Legend({ items }: { items: { name: string; color: string; value?: string; shape?: 'rect' | 'line' }[] }) {
  return (
    <ul className="legend" aria-label="Legend">
      {items.map((item) => (
        <li key={item.name}>
          <span
            className={`legend__key legend__key--${item.shape ?? 'rect'}`}
            style={{ background: item.color }}
            aria-hidden="true"
          />
          <span className="legend__name">{item.name}</span>
          {item.value !== undefined && <span className="legend__value">{item.value}</span>}
        </li>
      ))}
    </ul>
  )
}

interface TooltipEntry {
  dataKey?: string | number
  name?: string | number
  value?: unknown
  color?: string
}

interface ChartTooltipProps {
  active?: boolean
  label?: unknown
  payload?: TooltipEntry[]
  formatLabel?: (label: unknown) => string
  formatEntry: (key: string, value: CellValue) => string
}

/** Values lead, names follow; series keyed by a short line in the series color. */
export function ChartTooltip({ active, label, payload, formatLabel, formatEntry }: ChartTooltipProps) {
  if (!active || !payload?.length) return null
  return (
    <div className="chart-tooltip">
      {label !== undefined && label !== '' && (
        <div className="chart-tooltip__label">{formatLabel ? formatLabel(label) : String(label)}</div>
      )}
      {payload.map((entry) => {
        const key = String(entry.dataKey ?? entry.name ?? '')
        return (
          <div key={key} className="chart-tooltip__row">
            <span className="chart-tooltip__key" style={{ background: entry.color }} aria-hidden="true" />
            <strong>{formatEntry(key, (entry.value ?? null) as CellValue)}</strong>
            <span>{String(entry.name ?? key)}</span>
          </div>
        )
      })}
    </div>
  )
}

