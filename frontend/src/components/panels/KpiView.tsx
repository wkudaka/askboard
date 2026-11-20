import { formatValue } from '../../lib/format'
import type { PanelProps } from './chartUtils'

export function KpiView({ panel, format }: PanelProps) {
  const row = panel.rows[0] ?? []
  return (
    <div className="kpis">
      {panel.encoding.y.map((name) => {
        const index = panel.columns.findIndex((c) => c.name === name)
        return (
          <figure key={name} className="kpi" aria-label={name}>
            <figcaption className="kpi__label">{name}</figcaption>
            <div className="kpi__value">{formatValue(row[index] ?? null, panel.formats[name], format)}</div>
          </figure>
        )
      })}
    </div>
  )
}
