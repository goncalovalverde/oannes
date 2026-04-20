import { ChartErrorBoundary } from '../ui/ChartErrorBoundary'
import Plot from 'react-plotly.js'
import { darkLayout, plotConfig, TYPE_COLORS } from './plotConfig'
import type { CfdPoint } from '../../types'

interface Props { data: CfdPoint[] }

export default function CFDChart({ data }: Props) {
  if (!data?.length) return <div className="h-48 flex items-center justify-center text-muted text-sm">No data</div>

  const stages = [...new Set(data.map(d => d.stage))]
  const dates = [...new Set(data.map(d => d.date))].sort()

  const traces: Plotly.Data[] = stages.map((stage, i) => {
    const byDate = Object.fromEntries(data.filter(d => d.stage === stage).map(d => [d.date, d.count]))
    return {
      type: 'scatter', mode: 'lines', name: stage, stackgroup: 'one',
      x: dates, y: dates.map(d => byDate[d] ?? 0),
      line: { color: TYPE_COLORS[i % TYPE_COLORS.length] },
      fill: 'tonexty',
      fillcolor: TYPE_COLORS[i % TYPE_COLORS.length] + '40',
    }
  })

  return (
    <ChartErrorBoundary chartName="CFDChart">
      <Plot
        data={traces}
        layout={{ ...darkLayout } as any}
        config={plotConfig}
        style={{ width: '100%', height: '280px' }}
        useResizeHandler
      />
    </ChartErrorBoundary>
  )
}
