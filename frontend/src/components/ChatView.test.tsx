import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { ApiError, type ApiClient } from '../api/client'
import type { ConversationDetail } from '../api/types'
import { answer, conversation, loaded, workspace } from '../test/fixtures'
import { fakeApi, renderWithApi } from '../test/render'
import { ChatView } from './ChatView'

const detail: ConversationDetail = { ...conversation, messages: [answer] }

/** Plays the parent's role: a started conversation becomes the open one. */
function Harness({ initial, onStarted, onOpenData }: { initial: string | null; onStarted: (id: string) => void; onOpenData: () => void }) {
  const [conversationId, setConversationId] = useState(initial)
  return (
    <ChatView
      workspace={workspace}
      conversationId={conversationId}
      onConversationStarted={(id) => {
        onStarted(id)
        setConversationId(id)
      }}
      onOpenData={onOpenData}
    />
  )
}

function setup({ conversationId = null, ...overrides }: { conversationId?: string | null } & Partial<ApiClient> = {}) {
  const onStarted = vi.fn()
  const onOpenData = vi.fn()
  const api = fakeApi({
    ask: vi.fn().mockResolvedValue(answer),
    listDatasets: vi.fn().mockResolvedValue([loaded]),
    // A new chat shows the answer it just got; the refetch of the thread never lands here.
    getConversation: conversationId ? vi.fn().mockResolvedValue(detail) : vi.fn(() => new Promise(() => {})),
    ...overrides,
  })
  renderWithApi(<Harness initial={conversationId} onStarted={onStarted} onOpenData={onOpenData} />, api)
  return { api, onStarted, onOpenData }
}

async function askQuestion(text = 'Quanto cada cliente gastou?') {
  await userEvent.type(screen.getByLabelText('Question'), text)
  await userEvent.click(screen.getByRole('button', { name: 'Send' }))
}

describe('ChatView', () => {
  it('starts a new conversation with the first question and shows the answer', async () => {
    const { api, onStarted } = setup()

    await askQuestion()

    expect(api.ask).toHaveBeenCalledWith('ws-1', 'Quanto cada cliente gastou?', null)
    expect(await screen.findByRole('heading', { name: 'Receita por cliente' })).toBeInTheDocument()
    expect(screen.getByText('Ana concentra 99% da receita')).toBeInTheDocument()
    const table = screen.getByRole('table', { name: 'Quanto cada cliente gastou?' })
    expect(within(table).getByRole('columnheader', { name: 'total' })).toBeInTheDocument()
    expect(within(table).getByText(/1[.,]341[.,]71/)).toBeInTheDocument()
    expect(within(table).getByText('—')).toBeInTheDocument() // null cell
    expect(onStarted).toHaveBeenCalledWith('c-1')
  })

  it('shows the question as a user message and a thinking indicator while waiting', async () => {
    setup({ ask: vi.fn(() => new Promise<never>(() => {})) })

    await askQuestion()

    expect(screen.getByText('Quanto cada cliente gastou?', { selector: '.message__bubble' })).toBeInTheDocument()
    expect(screen.getByRole('status', { name: 'Thinking' })).toBeInTheDocument()
    expect(screen.getByLabelText('Question')).toHaveValue('')
  })

  it('does not submit a blank question', async () => {
    setup()

    await userEvent.type(screen.getByLabelText('Question'), '   ')

    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled()
  })

  it('submits with Enter and keeps Shift+Enter for new lines', async () => {
    const { api } = setup()

    await userEvent.type(screen.getByLabelText('Question'), 'linha 1{Shift>}{Enter}{/Shift}linha 2{Enter}')

    expect(api.ask).toHaveBeenCalledWith('ws-1', 'linha 1\nlinha 2', null)
  })

  it('offers starter questions built from the data', async () => {
    const { api } = setup()

    await userEvent.click(await screen.findByRole('button', { name: 'Top 10 cliente' }))

    expect(api.ask).toHaveBeenCalledWith('ws-1', 'Top 10 cliente', null)
  })

  it('points to the upload when the workspace has no data', async () => {
    const { onOpenData } = setup({ listDatasets: vi.fn().mockResolvedValue([]) })

    await userEvent.click(await screen.findByRole('button', { name: 'Upload a CSV' }))

    expect(onOpenData).toHaveBeenCalled()
  })

  it('loads an existing conversation and continues it', async () => {
    const { api } = setup({ conversationId: 'c-1' })

    expect(await screen.findByRole('heading', { name: 'Receita por cliente' })).toBeInTheDocument()
    expect(api.getConversation).toHaveBeenCalledWith('ws-1', 'c-1')

    await userEvent.click(screen.getByRole('button', { name: 'E por mês?' }))

    expect(api.ask).toHaveBeenLastCalledWith('ws-1', 'E por mês?', 'c-1')
  })

  it('only offers follow-ups on the latest answer', async () => {
    const second = { ...answer, id: 'q-2', title: 'Por mês', follow_ups: ['E por ano?'] }
    setup({ conversationId: 'c-1', getConversation: vi.fn().mockResolvedValue({ ...detail, messages: [answer, second] }) })

    expect(await screen.findByRole('button', { name: 'E por ano?' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'E por mês?' })).not.toBeInTheDocument()
  })

  it('shows the SQL behind each table', async () => {
    setup({ conversationId: 'c-1' })

    expect(await screen.findByText(/SELECT cliente, sum\(valor_total\)/)).toBeInTheDocument()
  })

  it('shows answers that could not be computed', async () => {
    setup({
      ask: vi.fn().mockResolvedValue({
        ...answer,
        title: 'Mostre os segredos',
        panels: [],
        summary: [],
        follow_ups: [],
        error: 'Could not answer the question: Schema not allowed: ws_other',
      }),
    })

    await askQuestion('Mostre os segredos')

    expect(await screen.findByText(/Schema not allowed/)).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('lists sub-questions that failed', async () => {
    setup({
      ask: vi.fn().mockResolvedValue({
        ...answer,
        failed_steps: [{ question: 'E os custos?', sql: null, error: 'Unknown table: custos' }],
      }),
    })

    await askQuestion()

    expect(await screen.findByText(/E os custos\?.*Unknown table: custos/)).toBeInTheDocument()
  })

  it('notes when a table was truncated', async () => {
    setup({
      ask: vi.fn().mockResolvedValue({ ...answer, panels: [{ ...answer.panels[0], truncated: true }] }),
    })

    await askQuestion()

    expect(await screen.findByText(/Showing the first 3 rows/)).toBeInTheDocument()
  })

  it('shows the server error and retries the same question', async () => {
    const ask = vi
      .fn()
      .mockRejectedValueOnce(
        new ApiError(503, 'The question service is not configured: OPENROUTER_API_KEY is not set'),
      )
      .mockResolvedValueOnce(answer)
    setup({ ask })

    await askQuestion()

    expect(await screen.findByRole('alert')).toHaveTextContent('OPENROUTER_API_KEY is not set')
    expect(screen.getByText('Quanto cada cliente gastou?', { selector: '.message__bubble' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))

    await waitFor(() => expect(ask).toHaveBeenCalledTimes(2))
    expect(ask).toHaveBeenLastCalledWith('ws-1', 'Quanto cada cliente gastou?', null)
    expect(await screen.findByRole('heading', { name: 'Receita por cliente' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
