import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import App from './App'
import { ApiError } from './api/client'
import { answer, conversation, workspace } from './test/fixtures'
import { fakeApi, renderWithApi } from './test/render'

function withWorkspace(overrides = {}) {
  return fakeApi({ listWorkspaces: vi.fn().mockResolvedValue([workspace]), ...overrides })
}

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

  it('welcomes a first-time user and offers to create a workspace', async () => {
    renderWithApi(<App />)

    expect(await screen.findByRole('heading', { name: 'Welcome to Askboard' })).toBeInTheDocument()
    expect(await screen.findByLabelText('Workspace name')).toBeInTheDocument()
  })

  it('shows the question box once a workspace is selected', async () => {
    renderWithApi(<App />, withWorkspace())

    expect(await screen.findByLabelText('Question')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'What do you want to know?' })).toBeInTheDocument()
  })

  it('opens the data panel with upload, datasets and relationships', async () => {
    renderWithApi(<App />, withWorkspace())

    await userEvent.click(await screen.findByRole('button', { name: 'Data' }))

    const panel = screen.getByRole('dialog', { name: 'Data' })
    expect(within(panel).getByLabelText('CSV file')).toBeInTheDocument()
    expect(await within(panel).findByText('No datasets yet. Upload a CSV to get started.')).toBeInTheDocument()
    expect(within(panel).getByRole('heading', { name: 'Relationships' })).toBeInTheDocument()
    expect(await within(panel).findByText(/No relationships detected yet/)).toBeInTheDocument()

    await userEvent.keyboard('{Escape}')

    expect(screen.queryByRole('dialog', { name: 'Data' })).not.toBeInTheDocument()
  })

  it('opens the upload from the composer', async () => {
    renderWithApi(<App />, withWorkspace())

    await userEvent.click(await screen.findByRole('button', { name: 'Upload CSV' }))

    expect(screen.getByRole('dialog', { name: 'Data' })).toBeInTheDocument()
  })

  it('opens a chat from the sidebar and goes back to a new chat', async () => {
    const api = withWorkspace({
      listConversations: vi.fn().mockResolvedValue([conversation]),
      getConversation: vi.fn().mockResolvedValue({ ...conversation, messages: [answer] }),
    })
    renderWithApi(<App />, api)

    await userEvent.click(await screen.findByRole('button', { name: 'Quanto cada cliente gastou?' }))

    expect(await screen.findByRole('heading', { name: 'Receita por cliente' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'New chat' }))

    expect(screen.getByRole('heading', { name: 'What do you want to know?' })).toBeInTheDocument()
  })

  it('moves a new chat into the sidebar after the first answer', async () => {
    const listConversations = vi.fn().mockResolvedValue([])
    const ask = vi.fn(async () => {
      listConversations.mockResolvedValue([conversation])
      return answer
    })
    renderWithApi(<App />, withWorkspace({ listConversations, ask }))

    await userEvent.type(await screen.findByLabelText('Question'), 'Quanto cada cliente gastou?{Enter}')

    const chats = screen.getByRole('navigation', { name: 'Chats' })
    await waitFor(() =>
      expect(within(chats).getByRole('button', { name: 'Quanto cada cliente gastou?' })).toHaveAttribute(
        'aria-current',
        'page',
      ),
    )
  })

  it('collapses and reopens the sidebar', async () => {
    renderWithApi(<App />, withWorkspace())

    await userEvent.click(await screen.findByRole('button', { name: 'Close sidebar' }))
    expect(screen.queryByRole('complementary', { name: 'Sidebar' })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Open sidebar' }))
    expect(screen.getByRole('complementary', { name: 'Sidebar' })).toBeInTheDocument()
  })
})
