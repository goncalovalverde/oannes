import { ChartErrorBoundary } from '../ui/ChartErrorBoundary'
import Plot from 'react-plotly.js'
import { darkLayout, plotConfig, COLORS, TYPE_COLORS } from './plotConfig'
import type { ThroughputPoint } from '../../types'

interface Props { data: ThroughputPoint[]; weeks: number; expanded?: boolean }

export default function ThroughputChart({ data, weeks, expanded = false }: Props) {
  if (!data?.length) return <div className="h-48 flex items-center justify-center text-muted text-sm">No data</div>

  const types = Object.keys(data[0]).filter(k => k !== 'week' && k !== 'Total')
  const weeks_x = data.map(d => d.week)

  const traces: Plotly.Data[] = types.map((t, i) => ({
    type: 'bar',
    name: t,
    x: weeks_x,
    y: data.map(d => d[t] ?? 0),
    marker: { color: TYPE_COLORS[i % TYPE_COLORS.length] },
  }))

  // Trendline on Total
  const totals = data.map(d => d.Total ?? 0)
  const n = totals.length
  if (n > 1) {
    const xIdx = totals.map((_, i) => i)
    const sumX = xIdx.reduce((a, b) => a + b, 0)
    const sumY = totals.reduce((a, b) => a + b, 0)
    const sumXY = xIdx.reduce((a, i) => a + i * totals[i], 0)
    const sumX2 = xIdx.reduce((a, i) => a + i * i, 0)
    const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX)
    const intercept = (sumY - slope * sumX) / n
    traces.push({
      type: 'scatter', mode: 'lines', name: 'Trend',
      x: weeks_x,
      y: xIdx.map(i => slope * i + intercept),
      line: { color: COLORS.purple, dash: 'dash', width: 2 },
      opacity: 0.7,
    })
  }

  return (
    <ChartErrorBoundary chartName="ThroughputChart">
      <Plot
        data={traces}
        layout={{ ...darkLayout, barmode: 'stack' } as any}
        config={plotConfig}
        style={{ width: '100%', height: expanded ? '400px' : '220px' }}
        useResizeHandler
      />
    </ChartErrorBoundary>
  )
}
