import type {
  AskRecord,
  ConfirmRequest,
  Dataset,
  DatasetPreview,
  Relationship,
  RelationshipStatus,
  Workspace,
} from './types'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export interface Readiness {
  status: 'ok'
}

export interface ApiClient {
  getReadiness(): Promise<Readiness>
  listWorkspaces(): Promise<Workspace[]>
  createWorkspace(name: string): Promise<Workspace>
  listDatasets(workspaceId: string): Promise<Dataset[]>
  uploadDataset(workspaceId: string, file: File): Promise<DatasetPreview>
  confirmDataset(workspaceId: string, datasetId: string, body: ConfirmRequest): Promise<Dataset>
  ask(workspaceId: string, question: string): Promise<AskRecord>
  listQuestions(workspaceId: string): Promise<AskRecord[]>
  listRelationships(workspaceId: string): Promise<Relationship[]>
  updateRelationship(workspaceId: string, relationshipId: string, status: RelationshipStatus): Promise<Relationship>
}

export interface ApiClientOptions {
  baseUrl: string
  fetch?: typeof fetch
}

function detailMessage(detail: unknown): string | null {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    // FastAPI validation errors: [{ msg, loc, ... }]
    const messages = detail
      .map((d) => (d && typeof d === 'object' && 'msg' in d ? String(d.msg) : null))
      .filter((m): m is string => m !== null)
    return messages.length ? messages.join('; ') : null
  }
  return null
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (body && typeof body === 'object' && 'detail' in body) {
      const message = detailMessage(body.detail)
      if (message) return message
    }
  } catch {
    // body was not JSON; fall back to the status text
  }
  return response.statusText || `HTTP ${response.status}`
}

const seg = encodeURIComponent

export function createApiClient({ baseUrl, fetch: fetchImpl = fetch }: ApiClientOptions): ApiClient {
  const root = baseUrl.replace(/\/+$/, '')

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    let response: Response
    try {
      response = await fetchImpl(`${root}${path}`, {
        ...init,
        headers: { Accept: 'application/json', ...(init.headers as Record<string, string>) },
      })
    } catch (cause) {
      throw new ApiError(0, cause instanceof Error ? cause.message : 'Network error')
    }
    if (!response.ok) {
      throw new ApiError(response.status, await errorMessage(response))
    }
    return (await response.json()) as T
  }

  function postJson<T>(path: string, body: unknown): Promise<T> {
    return request<T>(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  }

  return {
    getReadiness: () => request('/readyz'),
    listWorkspaces: () => request('/workspaces'),
    createWorkspace: (name) => postJson('/workspaces', { name }),
    listDatasets: (workspaceId) => request(`/workspaces/${seg(workspaceId)}/datasets`),
    uploadDataset: (workspaceId, file) => {
      const form = new FormData()
      form.append('file', file)
      // No Content-Type: the browser sets the multipart boundary itself.
      return request(`/workspaces/${seg(workspaceId)}/datasets`, { method: 'POST', body: form })
    },
    confirmDataset: (workspaceId, datasetId, body) =>
      postJson(`/workspaces/${seg(workspaceId)}/datasets/${seg(datasetId)}/confirm`, body),
    ask: (workspaceId, question) => postJson(`/workspaces/${seg(workspaceId)}/ask`, { question }),
    listQuestions: (workspaceId) => request(`/workspaces/${seg(workspaceId)}/questions`),
    listRelationships: (workspaceId) => request(`/workspaces/${seg(workspaceId)}/relationships`),
    updateRelationship: (workspaceId, relationshipId, status) =>
      request(`/workspaces/${seg(workspaceId)}/relationships/${seg(relationshipId)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      }),
  }
}
