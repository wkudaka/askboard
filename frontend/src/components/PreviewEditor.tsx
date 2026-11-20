import { useState, type FormEvent } from 'react'
import { PG_TYPES, type ColumnOverride, type ConfirmRequest, type DatasetPreview, type PgType } from '../api/types'

interface Props {
  preview: DatasetPreview
  submitting: boolean
  error: string | null
  onConfirm: (body: ConfirmRequest) => void
  onCancel: () => void
}

interface ColumnEdit {
  name: string
  pg_type: PgType
}

const DELIMITER_LABELS: Record<string, string> = { ',': 'comma', ';': 'semicolon', '\t': 'tab', '|': 'pipe' }

function buildConfirmRequest(
  preview: DatasetPreview,
  tableName: string,
  edits: Record<number, ColumnEdit>,
): ConfirmRequest {
  const columns: ColumnOverride[] = []
  for (const col of preview.columns) {
    const edit = edits[col.position]
    const override: ColumnOverride = { position: col.position }
    if (edit.name.trim() !== col.name) override.name = edit.name.trim()
    if (edit.pg_type !== col.pg_type) override.pg_type = edit.pg_type
    if (override.name !== undefined || override.pg_type !== undefined) columns.push(override)
  }
  const body: ConfirmRequest = { columns }
  if (tableName.trim() !== preview.table_name) body.table_name = tableName.trim()
  return body
}

export function PreviewEditor({ preview, submitting, error, onConfirm, onCancel }: Props) {
  const [tableName, setTableName] = useState(preview.table_name)
  const [edits, setEdits] = useState<Record<number, ColumnEdit>>(() =>
    Object.fromEntries(preview.columns.map((c) => [c.position, { name: c.name, pg_type: c.pg_type }])),
  )

  const skipped = preview.load_errors.filter((e) => e.column === null)
  const rowCount = preview.row_count ?? 0

  function edit(position: number, patch: Partial<ColumnEdit>) {
    setEdits((current) => ({ ...current, [position]: { ...current[position], ...patch } }))
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    onConfirm(buildConfirmRequest(preview, tableName, edits))
  }

  return (
    <form className="preview" onSubmit={submit}>
      <header className="preview__header">
        <h2>Review {preview.original_filename}</h2>
        <p className="muted">
          Detected {preview.source_format.encoding} ·{' '}
          {DELIMITER_LABELS[preview.source_format.delimiter] ?? preview.source_format.delimiter} separated ·{' '}
          {rowCount} rows
        </p>
      </header>

      <label className="field">
        <span>Table name</span>
        <input value={tableName} onChange={(e) => setTableName(e.target.value)} required />
      </label>

      {skipped.length > 0 && (
        <p className="notice notice--warn">
          {`${skipped.length} ${skipped.length === 1 ? 'row' : 'rows'} will be skipped (wrong number of columns): ` +
            `line ${skipped.map((e) => e.line).join(', ')}`}
        </p>
      )}

      <div className="table-scroll">
        <table aria-label="Columns" className="data-table">
          <thead>
            <tr>
              <th>CSV column</th>
              <th>Name</th>
              <th>Type</th>
              <th>Kind</th>
              <th>Sample values</th>
            </tr>
          </thead>
          <tbody>
            {preview.columns.map((col) => (
              <tr key={col.position}>
                <td>{col.original_name}</td>
                <td>
                  <input
                    aria-label={`Name for column ${col.original_name}`}
                    value={edits[col.position].name}
                    onChange={(e) => edit(col.position, { name: e.target.value })}
                    required
                  />
                </td>
                <td>
                  <select
                    aria-label={`Type for column ${col.original_name}`}
                    value={edits[col.position].pg_type}
                    onChange={(e) => edit(col.position, { pg_type: e.target.value as PgType })}
                  >
                    {PG_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <span className={`badge badge--${col.semantic_type}`}>{col.semantic_type}</span>
                </td>
                <td className="muted samples">{col.sample_values.join(' · ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3>First rows</h3>
      <div className="table-scroll">
        <table aria-label="Preview rows" className="data-table data-table--compact">
          <thead>
            <tr>
              {preview.columns.map((c) => (
                <th key={c.position}>{c.original_name}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {preview.preview_rows.map((row, i) => (
              <tr key={i}>
                {row.map((value, j) => (
                  <td key={j}>{value}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {error && <p role="alert">{error}</p>}

      <div className="actions">
        <button type="button" className="button--secondary" onClick={onCancel} disabled={submitting}>
          Cancel
        </button>
        <button type="submit" disabled={submitting}>
          {submitting ? 'Importing…' : `Import ${rowCount} rows`}
        </button>
      </div>
    </form>
  )
}
