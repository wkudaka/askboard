import { useQuery } from '@tanstack/react-query'
import { useApi } from '../api/ApiProvider'

export function ApiStatus() {
  const api = useApi()
  const readiness = useQuery({
    queryKey: ['readiness'],
    queryFn: () => api.getReadiness(),
    refetchInterval: 15_000,
  })

  if (readiness.isPending) {
    return (
      <p role="status" className="api-status api-status--pending">
        Checking API…
      </p>
    )
  }

  if (readiness.isError) {
    return (
      <p role="status" className="api-status api-status--offline">
        <span>API offline</span>
        <span className="api-status__detail"> — {readiness.error.message}</span>
      </p>
    )
  }

  return (
    <p role="status" className="api-status api-status--online">
      API online
    </p>
  )
}
