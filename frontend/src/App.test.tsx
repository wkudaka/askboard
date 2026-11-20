import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import App from './App'
import { ApiError } from './api/client'
import { workspace } from './test/fixtures'
import { fakeApi, renderWithApi } from './test/render'

describe('App', () => {
  it('shows the product name', () => {
    renderWithApi(<App />)

    expect(screen.getByRole('heading', { level: 1, name: 'Askboard' })).toBeInTheDocument()
  })

  it('shows the API as online when the backend is ready', async () => {
    renderWithApi(<App />)

    expect(await screen.findByText('API online')).toBeInTheDocument()
  })

  it('shows the API as offline when the backend is not ready', async () => {
    const api = fakeApi({
      getReadiness: vi.fn().mockRejectedValue(new ApiError(503, 'Database not reachable')),
    })
    renderWithApi(<App />, api)

    expect(await screen.findByText('API offline')).toBeInTheDocument()
    expect(screen.getByText(/Database not reachable/)).toBeInTheDocument()
  })

  it('shows a checking state before the readiness call resolves', () => {
    const api = fakeApi({ getReadiness: () => new Promise(() => {}) })
    renderWithApi(<App />, api)

    expect(screen.getByText('Checking API…')).toBeInTheDocument()
  })

  it('shows the upload area once a workspace is selected', async () => {
    const api = fakeApi({ listWorkspaces: vi.fn().mockResolvedValue([workspace]) })
    renderWithApi(<App />, api)

    expect(await screen.findByLabelText('CSV file')).toBeInTheDocument()
    expect(await screen.findByText('No datasets yet. Upload a CSV to get started.')).toBeInTheDocument()
  })

  it('shows detected relationships once a workspace is selected', async () => {
    const api = fakeApi({ listWorkspaces: vi.fn().mockResolvedValue([workspace]) })
    renderWithApi(<App />, api)

    expect(await screen.findByRole('heading', { name: 'Relationships' })).toBeInTheDocument()
    expect(await screen.findByText(/No relationships detected yet/)).toBeInTheDocument()
  })

  it('shows the question box once a workspace is selected', async () => {
    const api = fakeApi({ listWorkspaces: vi.fn().mockResolvedValue([workspace]) })
    renderWithApi(<App />, api)

    expect(await screen.findByLabelText('Question')).toBeInTheDocument()
  })
})
