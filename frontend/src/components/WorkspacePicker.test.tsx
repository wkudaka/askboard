import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { workspace } from '../test/fixtures'
import { fakeApi, renderWithApi } from '../test/render'
import { WorkspacePicker } from './WorkspacePicker'

describe('WorkspacePicker', () => {
  it('offers to create the first workspace when there are none', async () => {
    const onChange = vi.fn()
    const api = fakeApi({
      createWorkspace: vi.fn().mockResolvedValue({ ...workspace, id: 'ws-2', name: 'Ops' }),
    })
    renderWithApi(<WorkspacePicker value={null} onChange={onChange} />, api)

    await userEvent.type(await screen.findByLabelText('Workspace name'), 'Ops')
    await userEvent.click(screen.getByRole('button', { name: 'Create' }))

    expect(api.createWorkspace).toHaveBeenCalledWith('Ops')
    await waitFor(() => expect(onChange).toHaveBeenCalledWith('ws-2'))
  })

  it('does not submit a blank name', async () => {
    const api = fakeApi()
    renderWithApi(<WorkspacePicker value={null} onChange={vi.fn()} />, api)

    await userEvent.type(await screen.findByLabelText('Workspace name'), '   ')

    expect(screen.getByRole('button', { name: 'Create' })).toBeDisabled()
  })

  it('auto-selects the first existing workspace', async () => {
    const onChange = vi.fn()
    const api = fakeApi({ listWorkspaces: vi.fn().mockResolvedValue([workspace]) })
    renderWithApi(<WorkspacePicker value={null} onChange={onChange} />, api)

    await waitFor(() => expect(onChange).toHaveBeenCalledWith('ws-1'))
  })

  it('switches between workspaces', async () => {
    const onChange = vi.fn()
    const other = { ...workspace, id: 'ws-2', name: 'Ops' }
    const api = fakeApi({ listWorkspaces: vi.fn().mockResolvedValue([workspace, other]) })
    renderWithApi(<WorkspacePicker value="ws-1" onChange={onChange} />, api)

    await userEvent.selectOptions(await screen.findByLabelText('Workspace'), 'Ops')

    expect(onChange).toHaveBeenCalledWith('ws-2')
  })
})
