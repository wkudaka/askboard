import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type ChangeEvent, type DragEvent } from 'react'
import { useApi } from '../api/ApiProvider'
import type { ConfirmRequest, Dataset, DatasetPreview } from '../api/types'
import { PreviewEditor } from './PreviewEditor'

type Step =
  | { kind: 'idle' }
  | { kind: 'review'; preview: DatasetPreview }
  | { kind: 'done'; dataset: Dataset }

function plural(n: number, word: string) {
  return `${n} ${word}${n === 1 ? '' : 's'}`
}

export function DatasetUpload({ workspaceId }: { workspaceId: string }) {
  const api = useApi()
  const queryClient = useQueryClient()
  const [step, setStep] = useState<Step>({ kind: 'idle' })
  const [dragging, setDragging] = useState(false)

  const upload = useMutation({
    mutationFn: (file: File) => api.uploadDataset(workspaceId, file),
    onSuccess: (preview) => {
      setStep({ kind: 'review', preview })
      void queryClient.invalidateQueries({ queryKey: ['datasets', workspaceId] })
    },
  })
  const confirm = useMutation({
    mutationFn: ({ datasetId, body }: { datasetId: string; body: ConfirmRequest }) =>
      api.confirmDataset(workspaceId, datasetId, body),
    onSuccess: (dataset) => {
      setStep({ kind: 'done', dataset })
      void queryClient.invalidateQueries({ queryKey: ['datasets', workspaceId] })
    },
  })

  function start(file: File | undefined) {
    if (!file) return
    confirm.reset()
    upload.mutate(file)
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    start(event.target.files?.[0])
    event.target.value = '' // allow picking the same file again
  }

  function onDrop(event: DragEvent) {
    event.preventDefault()
    setDragging(false)
    start(event.dataTransfer.files[0])
  }

  if (step.kind === 'review') {
    return (
      <PreviewEditor
        preview={step.preview}
        submitting={confirm.isPending}
        error={confirm.isError ? confirm.error.message : null}
        onCancel={() => {
          confirm.reset()
          setStep({ kind: 'idle' })
        }}
        onConfirm={(body) => confirm.mutate({ datasetId: step.preview.id, body })}
      />
    )
  }

  return (
    <section className="upload">
      {step.kind === 'done' && (
        <div className="notice notice--ok">
          <p>
            Loaded {plural(step.dataset.row_count ?? 0, 'row')} into <code>{step.dataset.table_name}</code>
          </p>
          {step.dataset.rejected_rows > 0 && (
            <>
              <p>{`${plural(step.dataset.rejected_rows, 'row')} rejected:`}</p>
              <ul className="error-list">
                {step.dataset.load_errors.map((e, i) => (
                  <li key={i}>
                    {`Line ${e.line}${e.column ? ` · ${e.column}` : ''}: ${e.message}`}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

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
          {upload.isPending ? 'Reading file…' : 'Drop a CSV here or click to choose'}
        </span>
        <span className="muted">Comma, semicolon, tab or pipe separated · UTF-8 or Latin-1</span>
        <input
          type="file"
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
