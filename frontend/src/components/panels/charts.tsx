import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { CellValue } from '../../api/types'
import { allMonthStarts, formatCompact, formatDateTick, formatValue } from '../../lib/format'
import { toChartData } from '../../lib/pivot'
import { AXIS_TICK, GRID_STROKE, integerAxis, MAX_SERIES, seriesColor, valueFormatter, type PanelProps } from './chartUtils'
import { ChartTooltip, Legend } from './common'

const HEIGHT = 280
const HORIZONTAL_MIN_CATEGORIES = 9
const HORIZONTAL_MIN_LABEL = 13

function ChartFrame({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div role="img" aria-label={label} className="chart">
      {children}
    </div>
  )
}

function useXFormatter(panel: PanelProps['panel'], format: PanelProps['format']) {
  const xColumn = panel.columns.find((c) => c.name === panel.encoding.x)
  if (xColumn?.type === 'date' || xColumn?.type === 'timestamp') {
    const values = panel.rows.map((r) => r[panel.columns.indexOf(xColumn)])
    const monthStarts = allMonthStarts(values)
    return (v: unknown) => formatDateTick(v as CellValue, monthStarts, format)
  }
  return (v: unknown) => String(v)
}

export function BarChartView({ panel, format, stacked = false }: PanelProps & { stacked?: boolean }) {
  const { data, series } = toChartData(panel)
  const plotted = series.slice(0, MAX_SERIES)
  const x = panel.encoding.x ?? ''
  const formatX = useXFormatter(panel, format)
  const formatEntry = valueFormatter(panel, format)
  const longestLabel = Math.max(0, ...data.map((d) => formatX(d[x]).length))
  const horizontal = data.length >= HORIZONTAL_MIN_CATEGORIES || longestLabel >= HORIZONTAL_MIN_LABEL
  const height = horizontal ? Math.max(HEIGHT, data.length * 28 + 40) : HEIGHT
  const kind = stacked ? 'Stacked bar chart' : 'Bar chart'

  const categoryAxis = horizontal ? (
    <YAxis
      type="category"
      dataKey={x}
      tick={AXIS_TICK}
      tickFormatter={formatX}
      width={Math.min(180, longestLabel * 7 + 12)}
      axisLine={false}
      tickLine={false}
      interval={0}
    />
  ) : (
    <XAxis dataKey={x} tick={AXIS_TICK} tickFormatter={formatX} axisLine={{ stroke: GRID_STROKE }} tickLine={false} />
  )
  const valueAxis = horizontal ? (
    <XAxis type="number" allowDecimals={!integerAxis(panel)} tick={AXIS_TICK} tickFormatter={(v: number) => formatCompact(v, format)} axisLine={false} tickLine={false} />
  ) : (
    <YAxis allowDecimals={!integerAxis(panel)} tick={AXIS_TICK} tickFormatter={(v: number) => formatCompact(v, format)} axisLine={false} tickLine={false} width={56} />
  )

  return (
    <>
      {plotted.length > 1 && (
        <Legend items={plotted.map((name, i) => ({ name, color: seriesColor(i) }))} />
      )}
      <ChartFrame label={`${kind}: ${panel.title}`}>
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={data} layout={horizontal ? 'vertical' : 'horizontal'} margin={{ top: 8, right: 16, bottom: 4, left: 4 }}>
            <CartesianGrid stroke={GRID_STROKE} vertical={horizontal} horizontal={!horizontal} />
            {categoryAxis}
            {valueAxis}
            <Tooltip
              cursor={{ fill: 'var(--chart-hover)' }}
              content={<ChartTooltip formatLabel={formatX} formatEntry={formatEntry} />}
            />
            {plotted.map((name, i) => {
              const isTop = !stacked || i === plotted.length - 1
              const radius: [number, number, number, number] = !isTop
                ? [0, 0, 0, 0]
                : horizontal
                  ? [0, 4, 4, 0]
                  : [4, 4, 0, 0]
              return (
                <Bar
                  key={name}
                  dataKey={name}
                  name={name}
                  fill={seriesColor(i)}
                  stackId={stacked ? 'stack' : undefined}
                  maxBarSize={24}
                  radius={radius}
                  stroke="var(--chart-surface)"
                  strokeWidth={stacked ? 2 : 0}
                  isAnimationActive={false}
                />
              )
            })}
          </BarChart>
        </ResponsiveContainer>
      </ChartFrame>
    </>
  )
}

export function LineChartView({ panel, format }: PanelProps) {
  const { data, series } = toChartData(panel)
  const plotted = series.slice(0, MAX_SERIES)
  const x = panel.encoding.x ?? ''
  const formatX = useXFormatter(panel, format)
  const showDots = data.length <= 24

  return (
    <>
      {plotted.length > 1 && (
        <Legend items={plotted.map((name, i) => ({ name, color: seriesColor(i), shape: 'line' as const }))} />
      )}
      <ChartFrame label={`Line chart: ${panel.title}`}>
        <ResponsiveContainer width="100%" height={HEIGHT}>
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 4 }}>
            <CartesianGrid stroke={GRID_STROKE} vertical={false} />
            <XAxis dataKey={x} tick={AXIS_TICK} tickFormatter={formatX} axisLine={{ stroke: GRID_STROKE }} tickLine={false} minTickGap={16} />
            <YAxis allowDecimals={!integerAxis(panel)} tick={AXIS_TICK} tickFormatter={(v: number) => formatCompact(v, format)} axisLine={false} tickLine={false} width={56} />
            <Tooltip
              cursor={{ stroke: 'var(--text)', strokeWidth: 1 }}
              content={<ChartTooltip formatLabel={formatX} formatEntry={valueFormatter(panel, format)} />}
            />
            {plotted.map((name, i) => (
              <Line
                key={name}
                dataKey={name}
                name={name}
                type="linear"
                stroke={seriesColor(i)}
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
                dot={showDots ? { r: 4, fill: seriesColor(i), stroke: 'var(--chart-surface)', strokeWidth: 2 } : false}
                activeDot={{ r: 5, stroke: 'var(--chart-surface)', strokeWidth: 2 }}
                connectNulls
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </ChartFrame>
    </>
  )
}

export function PieChartView({ panel, format }: PanelProps) {
  const { data } = toChartData(panel)
  const x = panel.encoding.x ?? ''
  const y = panel.encoding.y[0] ?? ''
  // A missing value is not a zero-sized slice: leave it out of the whole.
  const slices = data
    .filter((d) => typeof d[y] === 'number')
    .slice(0, MAX_SERIES)
    .map((d) => ({ name: String(d[x]), value: d[y] as number }))
  const formatEntry = valueFormatter(panel, format)

  return (
    <div className="pie">
      <ChartFrame label={`Pie chart: ${panel.title}`}>
        <ResponsiveContainer width="100%" height={240}>
          <PieChart>
            <Pie
              data={slices}
              dataKey="value"
              nameKey="name"
              innerRadius="58%"
              outerRadius="88%"
              stroke="var(--chart-surface)"
              strokeWidth={2}
              isAnimationActive={false}
            >
              {slices.map((s, i) => (
                <Cell key={s.name} fill={seriesColor(i)} />
              ))}
            </Pie>
            <Tooltip content={<ChartTooltip formatEntry={(_, v) => formatEntry(y, v)} />} />
          </PieChart>
        </ResponsiveContainer>
      </ChartFrame>
      <Legend
        items={slices.map((s, i) => ({
          name: s.name,
          color: seriesColor(i),
          value: formatValue(s.value, panel.formats[y], format),
        }))}
      />
    </div>
  )
}

export function ScatterChartView({ panel, format }: PanelProps) {
  const x = panel.encoding.x ?? ''
  const y = panel.encoding.y[0] ?? ''
  const { data } = toChartData(panel)
  const formatEntry = valueFormatter(panel, format)

  return (
    <ChartFrame label={`Scatter chart: ${panel.title}`}>
      <ResponsiveContainer width="100%" height={HEIGHT}>
        <ScatterChart margin={{ top: 8, right: 16, bottom: 20, left: 4 }}>
          <CartesianGrid stroke={GRID_STROKE} />
          <XAxis
            type="number"
            dataKey={x}
            name={x}
            tick={AXIS_TICK}
            tickFormatter={(v: number) => formatCompact(v, format)}
            axisLine={{ stroke: GRID_STROKE }}
            tickLine={false}
            label={{ value: x, position: 'insideBottom', offset: -12, fill: 'var(--text)', fontSize: 12 }}
          />
          <YAxis
            type="number"
            dataKey={y}
            name={y}
            tick={AXIS_TICK}
            tickFormatter={(v: number) => formatCompact(v, format)}
            axisLine={false}
            tickLine={false}
            width={56}
          />
          <Tooltip
            cursor={{ strokeDasharray: undefined, stroke: GRID_STROKE }}
            content={<ChartTooltip formatEntry={formatEntry} />}
          />
          <Scatter
            data={data}
            fill={seriesColor(0)}
            stroke="var(--chart-surface)"
            strokeWidth={2}
            isAnimationActive={false}
          />
        </ScatterChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}
