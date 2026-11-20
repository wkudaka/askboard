import { useQuery } from '@tanstack/react-query'
import { useApi } from '../api/ApiProvider'

export function DatasetList({ workspaceId }: { workspaceId: string }) {
  const api = useApi()
  const datasets = useQuery({
    queryKey: ['datasets', workspaceId],
    queryFn: () => api.listDatasets(workspaceId),
  })

  if (datasets.isPending) return <p className="muted">Loading datasets…</p>
  if (datasets.isError) return <p role="alert">{datasets.error.message}</p>
  if (datasets.data.length === 0) {
    return <p className="muted">No datasets yet. Upload a CSV to get started.</p>
  }

  return (
    <div className="table-scroll">
      <table aria-label="Datasets" className="data-table">
        <thead>
          <tr>
            <th>Table</th>
            <th>File</th>
            <th>Status</th>
            <th className="num">Rows</th>
            <th className="num">Rejected</th>
            <th className="num">Columns</th>
          </tr>
        </thead>
        <tbody>
          {datasets.data.map((d) => (
            <tr key={d.id}>
              <td>
                <code>{d.table_name}</code>
              </td>
              <td>{d.original_filename}</td>
              <td>
                <span className={`badge badge--${d.status}`}>{d.status}</span>
              </td>
              <td className="num">{d.row_count ?? '—'}</td>
              <td className="num">{d.rejected_rows}</td>
              <td className="num">{d.columns.length}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
