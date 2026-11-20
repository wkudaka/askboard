import { describe, expect, it, vi } from 'vitest'
import { ApiError, createApiClient } from './client'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function setup(body: unknown = {}, status = 200) {
  // A fresh Response per call: a body can only be read once.
  const fetchMock = vi.fn().mockImplementation(async () => jsonResponse(body, status))
  const api = createApiClient({ baseUrl: 'http://api.test', fetch: fetchMock })
  return { api, fetchMock }
}

describe('createApiClient', () => {
  it('calls /readyz on the configured base URL', async () => {
    const { api, fetchMock } = setup({ status: 'ok' })

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
    const { api } = setup({ detail: 'Database not reachable' }, 503)

    const error = await api.getReadiness().catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(503)
    expect((error as ApiError).message).toBe('Database not reachable')
  })

  it('joins FastAPI validation errors into one message', async () => {
    const { api } = setup(
      { detail: [{ msg: 'Field required', loc: ['body', 'name'] }, { msg: 'Too short', loc: ['body', 'x'] }] },
      422,
    )

    const error = (await api.createWorkspace('').catch((e: unknown) => e)) as ApiError

    expect(error.status).toBe(422)
    expect(error.message).toBe('Field required; Too short')
  })

  it('throws ApiError with status 0 on network failure', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    const api = createApiClient({ baseUrl: 'http://api.test', fetch: fetchMock })

    const error = await api.getReadiness().catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(0)
  })

  it('creates a workspace with a JSON body', async () => {
    const { api, fetchMock } = setup({ id: 'ws-1', name: 'Sales' }, 201)

    await api.createWorkspace('Sales')

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('http://api.test/workspaces')
    expect(init.method).toBe('POST')
    expect(init.headers['Content-Type']).toBe('application/json')
    expect(JSON.parse(init.body)).toEqual({ name: 'Sales' })
  })

  it('lists workspaces and datasets', async () => {
    const { api, fetchMock } = setup([])

    await api.listWorkspaces()
    await api.listDatasets('ws-1')

    expect(fetchMock.mock.calls.map((c) => c[0])).toEqual([
      'http://api.test/workspaces',
      'http://api.test/workspaces/ws-1/datasets',
    ])
  })

  it('uploads a dataset as multipart form data without forcing a content type', async () => {
    const { api, fetchMock } = setup({ id: 'ds-1' }, 201)
    const file = new File(['a,b\n1,2\n'], 'orders.csv', { type: 'text/csv' })

    await api.uploadDataset('ws-1', file)

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('http://api.test/workspaces/ws-1/datasets')
    expect(init.method).toBe('POST')
    expect(init.body).toBeInstanceOf(FormData)
    expect((init.body as FormData).get('file')).toBe(file)
    expect(init.headers['Content-Type']).toBeUndefined()
  })

  it('confirms a dataset with overrides', async () => {
    const { api, fetchMock } = setup({ id: 'ds-1', status: 'loaded' })

    await api.confirmDataset('ws-1', 'ds-1', { columns: [{ position: 1, name: 'order_id' }] })

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('http://api.test/workspaces/ws-1/datasets/ds-1/confirm')
    expect(JSON.parse(init.body)).toEqual({ columns: [{ position: 1, name: 'order_id' }] })
  })

  it('posts a question to the workspace', async () => {
    const { api, fetchMock } = setup({ id: 'q-1' })

    await api.ask('ws-1', 'Quantos pedidos?')

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('http://api.test/workspaces/ws-1/ask')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toEqual({ question: 'Quantos pedidos?' })
  })

  it('lists previous questions', async () => {
    const { api, fetchMock } = setup([])

    await api.listQuestions('ws-1')

    expect(fetchMock.mock.calls[0][0]).toBe('http://api.test/workspaces/ws-1/questions')
  })

  it('encodes path segments', async () => {
    const { api, fetchMock } = setup([])

    await api.listDatasets('a/b')

    expect(fetchMock.mock.calls[0][0]).toBe('http://api.test/workspaces/a%2Fb/datasets')
  })
})
