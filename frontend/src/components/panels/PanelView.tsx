import { useState, type ComponentType } from 'react'
import type { Panel, PanelType } from '../../api/types'
import { BarChartView, LineChartView, PieChartView, ScatterChartView } from './charts'
import type { PanelProps } from './chartUtils'
import { KpiView } from './KpiView'
import { TableBody } from './TableBody'

const LABELS: Record<PanelType, string> = {
  kpi: 'Figures',
  bar: 'Bar',
  line: 'Line',
  pie: 'Pie',
  stacked_bar: 'Stacked bar',
  scatter: 'Scatter',
  table: 'Table',
}

const StackedBar = (props: PanelProps) => <BarChartView {...props} stacked />

/** Panel type -> component. The backend decides the type; this only renders it. */
const REGISTRY: Record<PanelType, ComponentType<PanelProps>> = {
  kpi: KpiView,
  bar: BarChartView,
  line: LineChartView,
  pie: PieChartView,
  stacked_bar: StackedBar,
  scatter: ScatterChartView,
  table: TableBody,
}

interface Props {
  panel: Panel
  currency: string | null
  locale?: string
}

export function PanelView({ panel, currency, locale }: Props) {
  const [view, setView] = useState<PanelType>(panel.type)
  const [shownType, setShownType] = useState<PanelType>(panel.type)
  if (shownType !== panel.type) {
    // A different panel arrived (e.g. history refetch): drop the old manual choice.
    setShownType(panel.type)
    setView(panel.type)
  }
  const options = [panel.type, ...panel.alternatives.filter((t) => t !== panel.type)]
  const Body = REGISTRY[view] ?? TableBody
  const format = { locale, currency }

  return (
    <div className={`panel panel--${view}`}>
      <div className="panel__header">
        <h4 className="panel__title">{panel.title}</h4>
        {options.length > 1 && (
          <div role="group" aria-label="Chart type" className="segmented">
            {options.map((type) => (
              <button
                key={type}
                type="button"
                aria-pressed={type === view}
                onClick={() => setView(type)}
              >
                {LABELS[type]}
              </button>
            ))}
          </div>
        )}
      </div>
      <Body panel={{ ...panel, type: view }} format={format} />
      {panel.truncated && <p className="muted">{`Showing the first ${panel.rows.length} rows`}</p>}
      <details className="panel__sql">
        <summary>SQL</summary>
        <pre>
          <code>{panel.sql}</code>
        </pre>
      </details>
    </div>
  )
}
