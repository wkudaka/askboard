import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'
import { useApi } from '../api/ApiProvider'
import { PlusIcon } from './icons'

interface Props {
  value: string | null
  onChange: (workspaceId: string) => void
}

export function WorkspacePicker({ value, onChange }: Props) {
  const api = useApi()
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [creating, setCreating] = useState(false)

  const workspaces = useQuery({ queryKey: ['workspaces'], queryFn: () => api.listWorkspaces() })
  const create = useMutation({
    mutationFn: (workspaceName: string) => api.createWorkspace(workspaceName),
    onSuccess: async (created) => {
      setName('')
      setCreating(false)
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

  if (workspaces.isPending) return <p className="sidebar__note">Loading workspaces…</p>
  if (workspaces.isError) return <p role="alert" className="sidebar__note">{workspaces.error.message}</p>

  const list = workspaces.data
  const showForm = list.length === 0 || creating

  return (
    <div className="workspace-picker">
      {list.length > 0 && (
        <div className="workspace-picker__row">
          <select aria-label="Workspace" value={value ?? ''} onChange={(e) => onChange(e.target.value)}>
            {list.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="icon-button"
            aria-label="New workspace"
            title="New workspace"
            aria-expanded={creating}
            onClick={() => setCreating((c) => !c)}
          >
            <PlusIcon />
          </button>
        </div>
      )}
      {showForm && (
        <form className="workspace-picker__create" onSubmit={submit}>
          {list.length === 0 && <p>Create your first workspace to start uploading data.</p>}
          <input
            aria-label="Workspace name"
            value={name}
            autoFocus={creating}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Sales 2024"
          />
          <button type="submit" disabled={!name.trim() || create.isPending}>
            Create
          </button>
          {create.isError && <p role="alert">{create.error.message}</p>}
        </form>
      )}
    </div>
  )
}
