import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import { useApi } from '../api/ApiProvider'
import type { ConfirmRequest, Dataset, DatasetPreview } from '../api/types'
import { PreviewEditor } from './PreviewEditor'

function plural(n: number, word: string) {
  return `${n} ${word}${n === 1 ? '' : 's'}`
}

function LoadSummary({ dataset }: { dataset: Dataset }) {
  return (
    <div className="notice notice--ok">
      <p>
        Loaded {plural(dataset.row_count ?? 0, 'row')} into <code>{dataset.table_name}</code>
      </p>
      {dataset.rejected_rows > 0 && (
        <>
          <p>{`${plural(dataset.rejected_rows, 'row')} rejected:`}</p>
          <ul className="error-list">
            {dataset.load_errors.map((e, i) => (
              <li key={i}>{`Line ${e.line}${e.column ? ` · ${e.column}` : ''}: ${e.message}`}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

export function DatasetUpload({ workspaceId }: { workspaceId: string }) {
  const api = useApi()
  const queryClient = useQueryClient()
  const [preview, setPreview] = useState<DatasetPreview | null>(null)
  const [lastLoaded, setLastLoaded] = useState<Dataset | null>(null)
  const [dragging, setDragging] = useState(false)
  // Files picked together are reviewed one at a time; the rest wait here.
  const queue = useRef<File[]>([])
  const [waiting, setWaiting] = useState(0)

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['datasets', workspaceId] })
    void queryClient.invalidateQueries({ queryKey: ['relationships', workspaceId] })
  }

  const upload = useMutation({
    mutationFn: (file: File) => api.uploadDataset(workspaceId, file),
    onSuccess: (result) => {
      setPreview(result)
      refresh()
    },
  })
  const confirm = useMutation({
    mutationFn: ({ datasetId, body }: { datasetId: string; body: ConfirmRequest }) =>
      api.confirmDataset(workspaceId, datasetId, body),
    onSuccess: (dataset) => {
      setLastLoaded(dataset)
      refresh()
      uploadNext()
    },
  })

  function uploadNext() {
    const file = queue.current.shift()
    setWaiting(queue.current.length)
    setPreview(null)
    confirm.reset()
    if (file) upload.mutate(file)
  }

  function start(files: FileList | File[] | null | undefined) {
    const picked = Array.from(files ?? [])
    if (picked.length === 0) return
    setLastLoaded(null)
    queue.current = picked
    uploadNext()
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    start(event.target.files)
    event.target.value = '' // allow picking the same files again
  }

  function onDrop(event: DragEvent) {
    event.preventDefault()
    setDragging(false)
    start(event.dataTransfer.files)
  }

  if (preview) {
    return (
      <>
        {lastLoaded && <LoadSummary dataset={lastLoaded} />}
        {waiting > 0 && <p className="muted">{`${plural(waiting, 'more file')} waiting`}</p>}
        <PreviewEditor
          key={preview.id}
          preview={preview}
          submitting={confirm.isPending}
          error={confirm.isError ? confirm.error.message : null}
          onCancel={uploadNext}
          onConfirm={(body) => confirm.mutate({ datasetId: preview.id, body })}
        />
      </>
    )
  }

  return (
    <section className="upload">
      {lastLoaded && <LoadSummary dataset={lastLoaded} />}

      <label
        className={`dropzone${dragging ? ' dropzone--active' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <span className="dropzone__title">
          {upload.isPending ? 'Reading file…' : 'Drop CSV files here or click to choose'}
        </span>
        <span className="muted">
          Several related files at once is fine · comma, semicolon, tab or pipe separated · UTF-8 or Latin-1
        </span>
        <input
          type="file"
          multiple
          accept=".csv,.tsv,.txt,text/csv"
          aria-label="CSV file"
          onChange={onFileChange}
          disabled={upload.isPending}
        />
      </label>
      {upload.isError && <p role="alert">{upload.error.message}</p>}
    </section>
  )
}
