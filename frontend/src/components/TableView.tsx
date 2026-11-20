import type { CellValue, ColumnKind, TablePanel } from '../api/types'

const numberFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 })

function formatCell(value: CellValue, kind: ColumnKind): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'number') return numberFormat.format(value)
  if (typeof value === 'boolean') return value ? 'yes' : 'no'
  if (kind === 'timestamp') return value.replace('T', ' ').replace(/\.\d+/, '')
  return String(value)
}

export function TableView({ panel }: { panel: TablePanel }) {
  return (
    <figure className="panel">
      <figcaption className="panel__title">{panel.title}</figcaption>
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
                {row.map((value, j) => (
                  <td key={j} className={panel.columns[j]?.type === 'number' ? 'num' : undefined}>
                    {formatCell(value, panel.columns[j]?.type ?? 'text')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {panel.truncated && <p className="muted">{`Showing the first ${panel.rows.length} rows`}</p>}
      <details className="panel__sql">
        <summary>SQL</summary>
        <pre>
          <code>{panel.sql}</code>
        </pre>
      </details>
    </figure>
  )
}
