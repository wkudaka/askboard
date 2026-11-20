import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { vi } from 'vitest'
import { ApiProvider } from '../api/ApiProvider'
import type { ApiClient } from '../api/client'

/** An ApiClient whose methods are all vi.fn() mocks, with sensible defaults. */
export function fakeApi(overrides: Partial<ApiClient> = {}): ApiClient {
  return {
    getReadiness: vi.fn().mockResolvedValue({ status: 'ok' }),
    listWorkspaces: vi.fn().mockResolvedValue([]),
    createWorkspace: vi.fn(),
    listDatasets: vi.fn().mockResolvedValue([]),
    uploadDataset: vi.fn(),
    confirmDataset: vi.fn(),
    ask: vi.fn(),
    listQuestions: vi.fn().mockResolvedValue([]),
    listRelationships: vi.fn().mockResolvedValue([]),
    updateRelationship: vi.fn(),
    listConversations: vi.fn().mockResolvedValue([]),
    getConversation: vi.fn(),
    renameConversation: vi.fn(),
    deleteConversation: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  }
}

export function renderWithApi(ui: ReactElement, api: ApiClient = fakeApi()) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return {
    api,
    ...render(
      <QueryClientProvider client={queryClient}>
        <ApiProvider client={api}>{ui}</ApiProvider>
      </QueryClientProvider>,
    ),
  }
}
