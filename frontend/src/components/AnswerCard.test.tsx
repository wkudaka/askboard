import { render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { AskRecord, Panel } from '../api/types'
import { answer } from '../test/fixtures'
import { AnswerCard } from './AnswerCard'

const kpi: Panel = {
  id: 'p2',
  type: 'kpi',
  title: 'Totais',
  sql: 'SELECT count(*) AS pedidos FROM pedidos',
  columns: [{ name: 'pedidos', type: 'number' }],
  rows: [[5]],
  truncated: false,
  encoding: { x: null, y: ['pedidos'], series: null },
  alternatives: ['table'],
  formats: { pedidos: 'integer' },
}

const dashboard: AskRecord = { ...answer, panels: [...answer.panels, kpi], currency: 'BRL' }

describe('AnswerCard dashboard layout', () => {
  it('puts key figures above the other panels', () => {
    render(<AnswerCard answer={dashboard} onFollowUp={vi.fn()} />)

    const figures = screen.getByRole('region', { name: 'Key figures' })
    const table = screen.getByRole('table', { name: 'Quanto cada cliente gastou?' })
    expect(within(figures).getByText('pedidos')).toBeInTheDocument()
    expect(figures.compareDocumentPosition(table) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('has no key figures region without KPI panels', () => {
    render(<AnswerCard answer={answer} onFollowUp={vi.fn()} />)

    expect(screen.queryByRole('region', { name: 'Key figures' })).not.toBeInTheDocument()
  })
})
