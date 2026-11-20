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
}

export interface ApiClientOptions {
  baseUrl: string
  fetch?: typeof fetch
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') {
      return body.detail
    }
  } catch {
    // body was not JSON; fall back to the status text
  }
  return response.statusText || `HTTP ${response.status}`
}

export function createApiClient({ baseUrl, fetch: fetchImpl = fetch }: ApiClientOptions): ApiClient {
  const root = baseUrl.replace(/\/+$/, '')

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    let response: Response
    try {
      response = await fetchImpl(`${root}${path}`, {
        ...init,
        headers: { Accept: 'application/json', ...init.headers },
      })
    } catch (cause) {
      throw new ApiError(0, cause instanceof Error ? cause.message : 'Network error')
    }
    if (!response.ok) {
      throw new ApiError(response.status, await errorMessage(response))
    }
    return (await response.json()) as T
  }

  return {
    getReadiness: () => request<Readiness>('/readyz'),
  }
}
