import { ChartErrorBoundary } from '../ui/ChartErrorBoundary'
import Plot from 'react-plotly.js'
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
