import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'
import { ApiError, type ApiClient } from './api/client'
import { ApiProvider } from './api/ApiProvider'

function renderApp(api: ApiClient) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <ApiProvider client={api}>
        <App />
      </ApiProvider>
    </QueryClientProvider>,
  )
}

const onlineApi: ApiClient = {
  getReadiness: async () => ({ status: 'ok' }),
}

const offlineApi: ApiClient = {
  getReadiness: async () => {
    throw new ApiError(503, 'Database not reachable')
  },
}

describe('App', () => {
  it('shows the product name', () => {
    renderApp(onlineApi)

    expect(screen.getByRole('heading', { level: 1, name: 'Askboard' })).toBeInTheDocument()
  })

  it('shows the API as online when the backend is ready', async () => {
    renderApp(onlineApi)

    expect(await screen.findByText('API online')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('API online')
  })

  it('shows the API as offline when the backend is not ready', async () => {
    renderApp(offlineApi)

    expect(await screen.findByText('API offline')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Database not reachable')
  })

  it('shows a checking state before the readiness call resolves', () => {
    const pendingApi: ApiClient = { getReadiness: () => new Promise(() => {}) }
    renderApp(pendingApi)

    expect(screen.getByRole('status')).toHaveTextContent('Checking API')
  })
})
