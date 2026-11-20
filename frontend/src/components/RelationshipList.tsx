import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useApi } from '../api/ApiProvider'
import type { Relationship, RelationshipStatus } from '../api/types'

function describe(r: Relationship) {
  return `${r.from_table}.${r.from_column} → ${r.to_table}.${r.to_column}`
}

export function RelationshipList({ workspaceId }: { workspaceId: string }) {
  const api = useApi()
  const queryClient = useQueryClient()
  const relationships = useQuery({
    queryKey: ['relationships', workspaceId],
    queryFn: () => api.listRelationships(workspaceId),
  })
  const update = useMutation({
    mutationFn: ({ id, status }: { id: string; status: RelationshipStatus }) =>
      api.updateRelationship(workspaceId, id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['relationships', workspaceId] }),
  })

  if (relationships.isPending) return <p className="muted">Looking for relationships…</p>
  if (relationships.isError) return <p role="alert">{relationships.error.message}</p>
  if (relationships.data.length === 0) {
    return (
      <p className="muted">
        No relationships detected yet. Upload related CSVs (for example orders with a <code>customer_id</code> and
        a customers file) and Askboard will suggest how to join them.
      </p>
    )
  }

  return (
    <ul className="relationships">
      {relationships.data.map((r) => {
        const label = describe(r)
        return (
          <li key={r.id} className={`relationship relationship--${r.status}`}>
            <code>{label}</code>
            <span className="muted">{`${Math.round(r.confidence * 100)}% of values match`}</span>
            <span className={`badge badge--${r.status}`}>{r.status}</span>
            <span className="relationship__actions">
              <button
                type="button"
                className="button--secondary"
                aria-label={`Confirm ${label}`}
                disabled={r.status === 'confirmed' || update.isPending}
                onClick={() => update.mutate({ id: r.id, status: 'confirmed' })}
              >
                Confirm
              </button>
              <button
                type="button"
                className="button--secondary"
                aria-label={`Reject ${label}`}
                disabled={r.status === 'rejected' || update.isPending}
                onClick={() => update.mutate({ id: r.id, status: 'rejected' })}
              >
                Reject
              </button>
            </span>
          </li>
        )
      })}
      {update.isError && <li role="alert">{update.error.message}</li>}
    </ul>
  )
}
