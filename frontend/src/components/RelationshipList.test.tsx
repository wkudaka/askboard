import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Relationship } from '../api/types'
import { fakeApi, renderWithApi } from '../test/render'
import { RelationshipList } from './RelationshipList'

const rel: Relationship = {
  id: 'r1',
  workspace_id: 'ws-1',
  from_dataset_id: 'd1',
  from_table: 'pedidos',
  from_column: 'cliente_id',
  to_dataset_id: 'd2',
  to_table: 'clientes',
  to_column: 'id',
  confidence: 0.96,
  status: 'suggested',
}

describe('RelationshipList', () => {
  it('explains how relationships appear when there are none', async () => {
    renderWithApi(<RelationshipList workspaceId="ws-1" />)

    expect(await screen.findByText(/No relationships detected yet/)).toBeInTheDocument()
  })

  it('lists suggested joins with their evidence', async () => {
    const api = fakeApi({ listRelationships: vi.fn().mockResolvedValue([rel]) })
    renderWithApi(<RelationshipList workspaceId="ws-1" />, api)

    expect(await screen.findByText('pedidos.cliente_id → clientes.id')).toBeInTheDocument()
    expect(screen.getByText('96% of values match')).toBeInTheDocument()
    expect(screen.getByText('suggested')).toBeInTheDocument()
    expect(api.listRelationships).toHaveBeenCalledWith('ws-1')
  })

  it('confirms a relationship', async () => {
    const api = fakeApi({
      listRelationships: vi.fn().mockResolvedValueOnce([rel]).mockResolvedValue([{ ...rel, status: 'confirmed' }]),
      updateRelationship: vi.fn().mockResolvedValue({ ...rel, status: 'confirmed' }),
    })
    renderWithApi(<RelationshipList workspaceId="ws-1" />, api)

    await userEvent.click(await screen.findByRole('button', { name: 'Confirm pedidos.cliente_id → clientes.id' }))

    expect(api.updateRelationship).toHaveBeenCalledWith('ws-1', 'r1', 'confirmed')
    await waitFor(() => expect(screen.getByText('confirmed')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'Confirm pedidos.cliente_id → clientes.id' })).toBeDisabled()
  })

  it('rejects a relationship', async () => {
    const api = fakeApi({
      listRelationships: vi.fn().mockResolvedValue([rel]),
      updateRelationship: vi.fn().mockResolvedValue({ ...rel, status: 'rejected' }),
    })
    renderWithApi(<RelationshipList workspaceId="ws-1" />, api)

    await userEvent.click(await screen.findByRole('button', { name: 'Reject pedidos.cliente_id → clientes.id' }))

    expect(api.updateRelationship).toHaveBeenCalledWith('ws-1', 'r1', 'rejected')
  })
})
