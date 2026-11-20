import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Panel } from '../../api/types'
import { PanelView } from './PanelView'

const base: Panel = {
  id: 'p1',
  type: 'pie',
  title: 'Receita por pagamento',
  sql: 'SELECT pagamento, sum(valor) AS receita FROM pedidos GROUP BY 1',
  columns: [
    { name: 'pagamento', type: 'text' },
    { name: 'receita', type: 'number' },
  ],
  rows: [
    ['pix', 50],
    ['boleto', 30],
    ['cartao', 20],
  ],
  truncated: false,
  encoding: { x: 'pagamento', y: ['receita'], series: null },
  alternatives: ['bar', 'table'],
  formats: { receita: 'currency' },
}

function renderPanel(panel: Partial<Panel> = {}, currency: string | null = null) {
  return render(<PanelView panel={{ ...base, ...panel }} currency={currency} locale="en-US" />)
}

describe('PanelView', () => {
  it('renders the chosen chart with its title', () => {
    renderPanel()

    expect(screen.getByRole('img', { name: 'Pie chart: Receita por pagamento' })).toBeInTheDocument()
    expect(screen.getByText('Receita por pagamento')).toBeInTheDocument()
  })

  it('offers the chart type and its alternatives', () => {
    renderPanel()

    const switcher = screen.getByRole('group', { name: 'Chart type' })
    const buttons = within(switcher).getAllByRole('button')
    expect(buttons.map((b) => b.textContent)).toEqual(['Pie', 'Bar', 'Table'])
    expect(within(switcher).getByRole('button', { name: 'Pie' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('switches to another view', async () => {
    renderPanel()

    await userEvent.click(screen.getByRole('button', { name: 'Table' }))

    expect(screen.getByRole('table', { name: 'Receita por pagamento' })).toBeInTheDocument()
    expect(screen.queryByRole('img', { name: /Pie chart/ })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Bar' }))

    expect(screen.getByRole('img', { name: 'Bar chart: Receita por pagamento' })).toBeInTheDocument()
  })

  it('has no switcher when there is nothing to switch to', () => {
    renderPanel({ type: 'table', alternatives: [] })

    expect(screen.queryByRole('group', { name: 'Chart type' })).not.toBeInTheDocument()
    expect(screen.getByRole('table')).toBeInTheDocument()
  })

  it('lists pie slices in a legend with formatted values', () => {
    renderPanel({}, 'USD')

    const legend = screen.getByRole('list', { name: 'Legend' })
    expect(within(legend).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      'pix$50.00',
      'boleto$30.00',
      'cartao$20.00',
    ])
  })

  it('leaves missing values out of pies instead of showing them as zero', () => {
    renderPanel({ rows: [['pix', 50], ['boleto', null]] }, 'USD')

    const legend = screen.getByRole('list', { name: 'Legend' })
    expect(within(legend).getAllByRole('listitem').map((li) => li.textContent)).toEqual(['pix$50.00'])
  })

  it('shows a legend for multi-series charts only', () => {
    const { unmount } = renderPanel({
      type: 'stacked_bar',
      columns: [
        { name: 'cidade', type: 'text' },
        { name: 'pagamento', type: 'text' },
        { name: 'receita', type: 'number' },
      ],
      rows: [
        ['Recife', 'pix', 10],
        ['Recife', 'boleto', 5],
        ['Natal', 'pix', 7],
      ],
      encoding: { x: 'cidade', y: ['receita'], series: 'pagamento' },
      alternatives: ['table'],
    })
    expect(within(screen.getByRole('list', { name: 'Legend' })).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      'pix',
      'boleto',
    ])
    unmount()

    renderPanel({ type: 'bar', alternatives: ['table'] })
    expect(screen.queryByRole('list', { name: 'Legend' })).not.toBeInTheDocument()
  })

  it('renders KPIs as labelled figures', () => {
    renderPanel(
      {
        type: 'kpi',
        columns: [
          { name: 'pedidos', type: 'number' },
          { name: 'receita', type: 'number' },
        ],
        rows: [[5, 1351.71]],
        encoding: { x: null, y: ['pedidos', 'receita'], series: null },
        alternatives: ['table'],
        formats: { pedidos: 'integer', receita: 'currency' },
      },
      'USD',
    )

    const figures = screen.getAllByRole('figure', { name: /pedidos|receita/ })
    expect(figures.map((f) => f.textContent)).toEqual(['pedidos5', 'receita$1,351.71'])
  })

  it('renders line, scatter and bar charts', () => {
    const { rerender } = render(
      <PanelView
        panel={{
          ...base,
          type: 'line',
          columns: [
            { name: 'mes', type: 'date' },
            { name: 'receita', type: 'number' },
          ],
          rows: [
            ['2024-01-01', 1],
            ['2024-02-01', 2],
            ['2024-03-01', 3],
            ['2024-04-01', 4],
          ],
          encoding: { x: 'mes', y: ['receita'], series: null },
          alternatives: ['bar', 'table'],
        }}
        currency={null}
        locale="en-US"
      />,
    )
    expect(screen.getByRole('img', { name: /^Line chart/ })).toBeInTheDocument()

    rerender(
      <PanelView
        panel={{
          ...base,
          type: 'scatter',
          columns: [
            { name: 'quantidade', type: 'number' },
            { name: 'valor', type: 'number' },
          ],
          rows: [
            [1, 2],
            [2, 4],
          ],
          encoding: { x: 'quantidade', y: ['valor'], series: null },
          alternatives: ['table'],
        }}
        currency={null}
        locale="en-US"
      />,
    )
    expect(screen.getByRole('img', { name: /^Scatter chart/ })).toBeInTheDocument()
  })

  it('keeps the SQL and truncation note', () => {
    renderPanel({ truncated: true })

    expect(screen.getByText(/SELECT pagamento/)).toBeInTheDocument()
    expect(screen.getByText('Showing the first 3 rows')).toBeInTheDocument()
  })
})
