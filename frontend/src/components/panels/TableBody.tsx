import { formatValue } from '../../lib/format'
import type { PanelProps } from './chartUtils'

export function TableBody({ panel, format }: PanelProps) {
  return (
    <div className="table-scroll">
      <table aria-label={panel.title} className="data-table">
        <thead>
          <tr>
            {panel.columns.map((c) => (
              <th key={c.name} className={c.type === 'number' ? 'num' : undefined}>
                {c.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {panel.rows.map((row, i) => (
            <tr key={i}>
              {row.map((value, j) => {
                const column = panel.columns[j]
                const text =
                  column?.type === 'timestamp' && typeof value === 'string'
                    ? value.replace('T', ' ').replace(/\.\d+/, '')
                    : formatValue(value, column ? panel.formats[column.name] : undefined, format)
                return (
                  <td key={j} className={column?.type === 'number' ? 'num' : undefined}>
                    {text}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
