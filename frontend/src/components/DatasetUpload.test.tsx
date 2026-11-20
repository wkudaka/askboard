import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import { loaded, preview } from '../test/fixtures'
import { fakeApi, renderWithApi } from '../test/render'
import { DatasetUpload } from './DatasetUpload'

const csv = new File(['ID;Cliente\n1;Ana\n'], 'pedidos.csv', { type: 'text/csv' })

async function uploadFile(apiOverrides = {}) {
  const api = fakeApi({
    uploadDataset: vi.fn().mockResolvedValue(preview),
    confirmDataset: vi.fn().mockResolvedValue(loaded),
    ...apiOverrides,
  })
  renderWithApi(<DatasetUpload workspaceId="ws-1" />, api)
  await userEvent.upload(screen.getByLabelText('CSV file'), csv)
  return api
}

describe('DatasetUpload', () => {
  it('uploads the chosen file to the workspace', async () => {
    const api = await uploadFile()

    expect(api.uploadDataset).toHaveBeenCalledWith('ws-1', csv)
  })

  it('shows the inferred schema for review', async () => {
    await uploadFile()

    expect(await screen.findByRole('heading', { name: 'Review pedidos.csv' })).toBeInTheDocument()
    expect(screen.getByLabelText('Table name')).toHaveValue('pedidos')
    expect(screen.getByLabelText('Name for column ID')).toHaveValue('id')
    expect(screen.getByLabelText('Type for column ID')).toHaveValue('bigint')
    expect(screen.getByLabelText('Type for column Valor Total')).toHaveValue('numeric')
    expect(screen.getByText('currency')).toBeInTheDocument()
    expect(screen.getByText(/cp1252/)).toBeInTheDocument()
  })

  it('shows preview rows and rows that will be skipped', async () => {
    await uploadFile()

    const table = await screen.findByRole('table', { name: 'Preview rows' })
    expect(within(table).getByText('R$ 10,00')).toBeInTheDocument()
    expect(screen.getByText(/1 row will be skipped/)).toBeInTheDocument()
    expect(screen.getByText(/line 6/)).toBeInTheDocument()
  })

  it('confirms with only the fields the user changed', async () => {
    const api = await uploadFile()

    const name = await screen.findByLabelText('Name for column ID')
    await userEvent.clear(name)
    await userEvent.type(name, 'order_id')
    await userEvent.selectOptions(screen.getByLabelText('Type for column Data do Pedido'), 'text')
    await userEvent.click(screen.getByRole('button', { name: 'Import 5 rows' }))

    expect(api.confirmDataset).toHaveBeenCalledWith('ws-1', 'ds-1', {
      columns: [
        { position: 1, name: 'order_id' },
        { position: 4, pg_type: 'text' },
      ],
    })
  })

  it('sends a changed table name', async () => {
    const api = await uploadFile()

    const tableName = await screen.findByLabelText('Table name')
    await userEvent.clear(tableName)
    await userEvent.type(tableName, 'orders')
    await userEvent.click(screen.getByRole('button', { name: 'Import 5 rows' }))

    expect(api.confirmDataset).toHaveBeenCalledWith('ws-1', 'ds-1', { table_name: 'orders', columns: [] })
  })

  it('shows the load summary with rejected rows', async () => {
    await uploadFile()

    await userEvent.click(await screen.findByRole('button', { name: 'Import 5 rows' }))

    expect(await screen.findByText(/Loaded 4 rows into/)).toBeInTheDocument()
    expect(screen.getByText(/2 rows rejected/)).toBeInTheDocument()
    expect(screen.getByText(/Not a number: 'A3'/)).toBeInTheDocument()
    expect(screen.getByLabelText('CSV file')).toBeInTheDocument() // ready for the next file
  })

  it('shows the server reason when the upload is rejected', async () => {
    await uploadFile({
      uploadDataset: vi.fn().mockRejectedValue(new ApiError(422, 'The file looks binary, not a CSV text file')),
    })

    expect(await screen.findByRole('alert')).toHaveTextContent('The file looks binary')
  })

  it('shows the server reason when the import fails', async () => {
    await uploadFile({
      confirmDataset: vi.fn().mockRejectedValue(new ApiError(422, "Duplicate column name(s): cliente")),
    })

    await userEvent.click(await screen.findByRole('button', { name: 'Import 5 rows' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Duplicate column name(s): cliente')
    expect(screen.getByRole('heading', { name: 'Review pedidos.csv' })).toBeInTheDocument()
  })

  it('reviews several files one after the other', async () => {
    const second = new File(['id;nome\n1;Ana\n'], 'clientes.csv', { type: 'text/csv' })
    const api = fakeApi({
      uploadDataset: vi
        .fn()
        .mockResolvedValueOnce(preview)
        .mockResolvedValueOnce({ ...preview, id: 'ds-2', original_filename: 'clientes.csv', table_name: 'clientes' }),
      confirmDataset: vi.fn().mockResolvedValue(loaded),
    })
    renderWithApi(<DatasetUpload workspaceId="ws-1" />, api)

    await userEvent.upload(screen.getByLabelText('CSV file'), [csv, second])

    expect(await screen.findByRole('heading', { name: 'Review pedidos.csv' })).toBeInTheDocument()
    expect(screen.getByText('1 more file waiting')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Import 5 rows' }))

    expect(await screen.findByRole('heading', { name: 'Review clientes.csv' })).toBeInTheDocument()
    expect(api.uploadDataset).toHaveBeenNthCalledWith(2, 'ws-1', second)
    expect(screen.getByText(/Loaded 4 rows into/)).toBeInTheDocument()
  })

  it('skips to the next file when a review is cancelled', async () => {
    const second = new File(['id;nome\n1;Ana\n'], 'clientes.csv', { type: 'text/csv' })
    const api = fakeApi({
      uploadDataset: vi
        .fn()
        .mockResolvedValueOnce(preview)
        .mockResolvedValueOnce({ ...preview, id: 'ds-2', original_filename: 'clientes.csv' }),
    })
    renderWithApi(<DatasetUpload workspaceId="ws-1" />, api)

    await userEvent.upload(screen.getByLabelText('CSV file'), [csv, second])
    await userEvent.click(await screen.findByRole('button', { name: 'Cancel' }))

    expect(await screen.findByRole('heading', { name: 'Review clientes.csv' })).toBeInTheDocument()
  })

  it('can cancel the review', async () => {
    await uploadFile()

    await userEvent.click(await screen.findByRole('button', { name: 'Cancel' }))

    expect(screen.queryByRole('heading', { name: 'Review pedidos.csv' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('CSV file')).toBeInTheDocument()
  })
})
