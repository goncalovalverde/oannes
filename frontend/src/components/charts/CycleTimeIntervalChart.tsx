import { ChartErrorBoundary } from '../ui/ChartErrorBoundary'
import Plot from './Plot'
import { darkLayout, plotConfig, COLORS } from './plotConfig'

interface CycleTimeIntervalData {
  period: string
  avg_cycle_time: number
}

interface Props {
  data: CycleTimeIntervalData[]
}

export default function CycleTimeIntervalChart({ data }: Props) {
  if (!data?.length) return <div className="h-48 flex items-center justify-center text-muted text-sm">No data</div>

  const periods = data.map(d => d.period)
  const avgCycleTimes = data.map(d => d.avg_cycle_time)

  const traces: Plotly.Data[] = [
    {
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Avg Cycle Time',
      x: periods,
      y: avgCycleTimes,
      line: { color: COLORS.teal, width: 2 },
      marker: { size: 6, color: COLORS.teal },
      fill: 'tozeroy',
      fillcolor: `${COLORS.teal}20`,
    },
  ]

  // Linear trendline (least squares)
  const n = avgCycleTimes.length
  if (n >= 2) {
    const sumX = avgCycleTimes.reduce((acc, _, i) => acc + i, 0)
    const sumY = avgCycleTimes.reduce((acc, v) => acc + v, 0)
    const sumXY = avgCycleTimes.reduce((acc, v, i) => acc + i * v, 0)
    const sumX2 = avgCycleTimes.reduce((acc, _, i) => acc + i * i, 0)
    const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX)
    const intercept = (sumY - slope * sumX) / n

    const extendFactor = 0.05
    const minX = -extendFactor * (n - 1)
    const maxX = (n - 1) * (1 + extendFactor)
    const trendX = [minX, maxX]
    const trendY = trendX.map(i => slope * i + intercept)

    traces.push({
      type: 'scatter', mode: 'lines', name: 'Trend',
      x: trendX.map(i => periods[Math.round(i)] || (i < 0 ? periods[0] : periods[n - 1])),
      y: trendY,
      line: { color: COLORS.purple, dash: 'dash', width: 2 },
      opacity: 0.7,
    })
  }

  return (
    <ChartErrorBoundary chartName="CycleTimeIntervalChart">
      <Plot
        data={traces}
        layout={{ ...darkLayout } as any}
        config={plotConfig}
        style={{ width: '100%', height: '220px' }}
        useResizeHandler
      />
    </ChartErrorBoundary>
  )
}
