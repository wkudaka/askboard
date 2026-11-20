import { describe, expect, it, vi } from 'vitest'
import { ApiError, createApiClient } from './client'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('createApiClient', () => {
  it('calls /readyz on the configured base URL', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ status: 'ok' }))
    const api = createApiClient({ baseUrl: 'http://api.test', fetch: fetchMock })

    const result = await api.getReadiness()

    expect(result).toEqual({ status: 'ok' })
    expect(fetchMock).toHaveBeenCalledWith('http://api.test/readyz', expect.any(Object))
  })

  it('strips a trailing slash from the base URL', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ status: 'ok' }))
    const api = createApiClient({ baseUrl: 'http://api.test/', fetch: fetchMock })

    await api.getReadiness()

    expect(fetchMock).toHaveBeenCalledWith('http://api.test/readyz', expect.any(Object))
  })

  it('throws ApiError with the HTTP status on non-2xx responses', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ detail: 'Database not reachable' }, 503))
    const api = createApiClient({ baseUrl: 'http://api.test', fetch: fetchMock })

    const error = await api.getReadiness().catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(503)
    expect((error as ApiError).message).toBe('Database not reachable')
  })

  it('throws ApiError with status 0 on network failure', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    const api = createApiClient({ baseUrl: 'http://api.test', fetch: fetchMock })

    const error = await api.getReadiness().catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(0)
  })
})
