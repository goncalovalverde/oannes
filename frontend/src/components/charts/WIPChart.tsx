import { ChartErrorBoundary } from '../ui/ChartErrorBoundary'
import Plot from './Plot'
import { darkLayout, plotConfig, TYPE_COLORS } from './plotConfig'
import type { WipPoint } from '../../types'

interface Props { data: WipPoint[] }

export default function WIPChart({ data }: Props) {
  if (!data?.length) return <div className="h-48 flex items-center justify-center text-muted text-sm">No data</div>

  const stages = [...new Set(data.map(d => d.stage))]
  const dates = [...new Set(data.map(d => d.date))].sort()

  const traces: Plotly.Data[] = stages.map((stage, i) => {
    const stageData = data.filter(d => d.stage === stage)
    const byDate = Object.fromEntries(stageData.map(d => [d.date, d.count]))
    return {
      type: 'bar', name: stage,
      x: dates, y: dates.map(d => byDate[d] ?? 0),
      marker: { color: TYPE_COLORS[i % TYPE_COLORS.length] },
    }
  })

  return (
    <ChartErrorBoundary chartName="WIPChart">
      <Plot
        data={traces}
        layout={{ ...darkLayout, barmode: 'stack' } as any}
        config={plotConfig}
        style={{ width: '100%', height: '220px' }}
        useResizeHandler
      />
    </ChartErrorBoundary>
  )
}
