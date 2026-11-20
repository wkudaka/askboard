import { screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { loaded, preview } from '../test/fixtures'
import { fakeApi, renderWithApi } from '../test/render'
import { DatasetList } from './DatasetList'

describe('DatasetList', () => {
  it('shows an empty state', async () => {
    renderWithApi(<DatasetList workspaceId="ws-1" />)

    expect(await screen.findByText('No datasets yet. Upload a CSV to get started.')).toBeInTheDocument()
  })

  it('lists datasets with status and row counts', async () => {
    const api = fakeApi({
      listDatasets: vi.fn().mockResolvedValue([loaded, { ...preview, id: 'ds-2', table_name: 'clientes' }]),
    })
    renderWithApi(<DatasetList workspaceId="ws-1" />, api)

    const table = await screen.findByRole('table', { name: 'Datasets' })
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(2)
    expect(rows[0]).toHaveTextContent('pedidos')
    expect(rows[0]).toHaveTextContent('loaded')
    expect(rows[0]).toHaveTextContent('4')
    expect(rows[1]).toHaveTextContent('clientes')
    expect(rows[1]).toHaveTextContent('pending')
    expect(api.listDatasets).toHaveBeenCalledWith('ws-1')
  })
})
