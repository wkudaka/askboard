import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'
import { useApi } from '../api/ApiProvider'

interface Props {
  value: string | null
  onChange: (workspaceId: string) => void
}

export function WorkspacePicker({ value, onChange }: Props) {
  const api = useApi()
  const queryClient = useQueryClient()
  const [name, setName] = useState('')

  const workspaces = useQuery({ queryKey: ['workspaces'], queryFn: () => api.listWorkspaces() })
  const create = useMutation({
    mutationFn: (workspaceName: string) => api.createWorkspace(workspaceName),
    onSuccess: async (created) => {
      setName('')
      await queryClient.invalidateQueries({ queryKey: ['workspaces'] })
      onChange(created.id)
    },
  })

  const firstId = workspaces.data?.[0]?.id
  useEffect(() => {
    if (value === null && firstId) onChange(firstId)
  }, [value, firstId, onChange])

  function submit(event: FormEvent) {
    event.preventDefault()
    if (name.trim()) create.mutate(name.trim())
  }

  if (workspaces.isPending) return <p className="muted">Loading workspaces…</p>
  if (workspaces.isError) return <p role="alert">{workspaces.error.message}</p>

  const list = workspaces.data

  return (
    <div className="workspace-picker">
      {list.length > 0 && (
        <label className="field">
          <span>Workspace</span>
          <select value={value ?? ''} onChange={(e) => onChange(e.target.value)}>
            {list.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
        </label>
      )}
      <form className="workspace-picker__create" onSubmit={submit}>
        {list.length === 0 && <p>Create your first workspace to start uploading data.</p>}
        <label className="field">
          <span>{list.length === 0 ? 'Workspace name' : 'New workspace'}</span>
          <input
            aria-label="Workspace name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Sales 2024"
          />
        </label>
        <button type="submit" disabled={!name.trim() || create.isPending}>
          Create
        </button>
        {create.isError && <p role="alert">{create.error.message}</p>}
      </form>
    </div>
  )
}
