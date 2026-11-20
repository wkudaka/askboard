import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { conversation } from '../test/fixtures'
import { fakeApi, renderWithApi } from '../test/render'
import { ConversationList } from './ConversationList'

const today = new Date().toISOString()
const chats = [
  { ...conversation, updated_at: today },
  { ...conversation, id: 'c-2', title: 'Pedidos por mês', updated_at: '2020-03-01T10:00:00Z' },
]

function setup(activeId: string | null = null, overrides = {}) {
  const onSelect = vi.fn()
  const api = fakeApi({ listConversations: vi.fn().mockResolvedValue(chats), ...overrides })
  renderWithApi(<ConversationList workspaceId="ws-1" activeId={activeId} onSelect={onSelect} />, api)
  return { api, onSelect }
}

describe('ConversationList', () => {
  it('groups chats by date and opens one when clicked', async () => {
    const { onSelect } = setup()

    const todayGroup = await screen.findByRole('region', { name: 'Today' })
    expect(within(todayGroup).getByText('Quanto cada cliente gastou?')).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: '2020' })).getByText('Pedidos por mês')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Pedidos por mês' }))

    expect(onSelect).toHaveBeenCalledWith('c-2')
  })

  it('marks the active chat', async () => {
    setup('c-2')

    expect(await screen.findByRole('button', { name: 'Pedidos por mês' })).toHaveAttribute('aria-current', 'page')
  })

  it('says when there are no chats', async () => {
    setup(null, { listConversations: vi.fn().mockResolvedValue([]) })

    expect(await screen.findByText('No chats yet.')).toBeInTheDocument()
  })

  it('renames a chat with Enter, once', async () => {
    const { api } = setup(null, {
      renameConversation: vi.fn().mockResolvedValue({ ...chats[1], title: 'Mensal' }),
    })

    await userEvent.click(await screen.findByRole('button', { name: 'Rename Pedidos por mês' }))
    const input = screen.getByLabelText('Chat title')
    await userEvent.clear(input)
    await userEvent.type(input, 'Mensal{Enter}')

    expect(await screen.findByRole('button', { name: 'Mensal' })).toBeInTheDocument()
    expect(api.renameConversation).toHaveBeenCalledTimes(1)
    expect(api.renameConversation).toHaveBeenCalledWith('ws-1', 'c-2', 'Mensal')
  })

  it('cancels a rename with Escape', async () => {
    const { api } = setup()

    await userEvent.click(await screen.findByRole('button', { name: 'Rename Pedidos por mês' }))
    await userEvent.type(screen.getByLabelText('Chat title'), ' x{Escape}')

    expect(screen.getByRole('button', { name: 'Pedidos por mês' })).toBeInTheDocument()
    expect(api.renameConversation).not.toHaveBeenCalled()
  })

  it('asks for confirmation before deleting, and leaves the deleted active chat', async () => {
    const { api, onSelect } = setup('c-2')

    await userEvent.click(await screen.findByRole('button', { name: 'Delete Pedidos por mês' }))
    expect(api.deleteConversation).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }))

    await waitFor(() => expect(screen.queryByText('Pedidos por mês')).not.toBeInTheDocument())
    expect(api.deleteConversation).toHaveBeenCalledWith('ws-1', 'c-2')
    expect(onSelect).toHaveBeenCalledWith(null)
  })

  it('can cancel a delete', async () => {
    const { api } = setup()

    await userEvent.click(await screen.findByRole('button', { name: 'Delete Pedidos por mês' }))
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.getByRole('button', { name: 'Pedidos por mês' })).toBeInTheDocument()
    expect(api.deleteConversation).not.toHaveBeenCalled()
  })
})
