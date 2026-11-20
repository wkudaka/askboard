import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import { answer } from '../test/fixtures'
import { fakeApi, renderWithApi } from '../test/render'
import { AskPanel } from './AskPanel'

function setup(overrides = {}) {
  const api = fakeApi({ ask: vi.fn().mockResolvedValue(answer), ...overrides })
  renderWithApi(<AskPanel workspaceId="ws-1" />, api)
  return api
}

async function askQuestion(text = 'Quanto cada cliente gastou?') {
  await userEvent.type(screen.getByLabelText('Question'), text)
  await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
}

describe('AskPanel', () => {
  it('sends the question and shows the answer', async () => {
    const api = setup()

    await askQuestion()

    expect(api.ask).toHaveBeenCalledWith('ws-1', 'Quanto cada cliente gastou?')
    expect(await screen.findByRole('heading', { name: 'Receita por cliente' })).toBeInTheDocument()
    expect(screen.getByText('Ana concentra 99% da receita')).toBeInTheDocument()
    const table = screen.getByRole('table', { name: 'Quanto cada cliente gastou?' })
    expect(within(table).getByRole('columnheader', { name: 'total' })).toBeInTheDocument()
    expect(within(table).getByText(/1[.,]341[.,]71/)).toBeInTheDocument()
    expect(within(table).getByText('—')).toBeInTheDocument() // null cell
  })

  it('clears the box after asking', async () => {
    setup()

    await askQuestion()

    await waitFor(() => expect(screen.getByLabelText('Question')).toHaveValue(''))
  })

  it('does not submit a blank question', async () => {
    setup()

    await userEvent.type(screen.getByLabelText('Question'), '   ')

    expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled()
  })

  it('submits with Enter and keeps Shift+Enter for new lines', async () => {
    const api = setup()

    await userEvent.type(screen.getByLabelText('Question'), 'linha 1{Shift>}{Enter}{/Shift}linha 2{Enter}')

    expect(api.ask).toHaveBeenCalledWith('ws-1', 'linha 1\nlinha 2')
  })

  it('shows the SQL behind each table', async () => {
    setup()

    await askQuestion()

    expect(await screen.findByText(/SELECT cliente, sum\(valor_total\)/)).toBeInTheDocument()
  })

  it('asks a follow-up question when clicked', async () => {
    const api = setup()
    await askQuestion()

    await userEvent.click(await screen.findByRole('button', { name: 'E por mês?' }))

    expect(api.ask).toHaveBeenLastCalledWith('ws-1', 'E por mês?')
  })

  it('shows previous answers on load', async () => {
    setup({ listQuestions: vi.fn().mockResolvedValue([answer]) })

    expect(await screen.findByRole('heading', { name: 'Receita por cliente' })).toBeInTheDocument()
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

  it('shows the server error when asking fails', async () => {
    setup({
      ask: vi
        .fn()
        .mockRejectedValue(
          new ApiError(503, 'The question service is not configured: OPENROUTER_API_KEY is not set'),
        ),
    })

    await askQuestion()

    expect(await screen.findByRole('alert')).toHaveTextContent('OPENROUTER_API_KEY is not set')
  })
})
