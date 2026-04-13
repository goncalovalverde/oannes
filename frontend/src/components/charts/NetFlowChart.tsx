import { ChartErrorBoundary } from '../ui/ChartErrorBoundary'
import Plot from 'react-plotly.js'
import { darkLayout, plotConfig } from './plotConfig'

interface NetFlowPoint {
  week: string
  arrivals: number
  completions: number
  net: number
}

interface Props {
  data: NetFlowPoint[]
}

export default function NetFlowChart({ data }: Props) {
  if (!data?.length) {
    return (
      <div className="h-48 flex items-center justify-center text-muted text-sm">
        No data
      </div>
    )
  }

  const weeks = data.map(d => d.week)

  const traces: Plotly.Data[] = [
    {
      type: 'bar',
      name: 'Arrivals',
      x: weeks,
      y: data.map(d => d.arrivals),
      marker: { color: '#6366f1', opacity: 0.75 },
    },
    {
      type: 'bar',
      name: 'Completions',
      x: weeks,
      y: data.map(d => d.completions),
      marker: { color: '#22c55e', opacity: 0.75 },
    },
    {
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Net Flow',
      x: weeks,
      y: data.map(d => d.net),
      yaxis: 'y2',
      line: { color: '#f59e0b', width: 2 },
      marker: { size: 5, color: data.map(d => (d.net >= 0 ? '#22c55e' : '#ef4444')) },
    },
  ]

  const layout: Partial<Plotly.Layout> = {
    ...darkLayout,
    barmode: 'group',
    yaxis: { ...darkLayout.yaxis, title: { text: 'Items' } as any, tickfont: { size: 10 } },
    yaxis2: {
      overlaying: 'y' as const,
      side: 'right' as const,
      title: { text: 'Net Flow' } as any,
      tickfont: { size: 10, color: '#f59e0b' },
      zeroline: true,
      zerolinecolor: '#f59e0b',
      zerolinewidth: 1,
      showgrid: false,
    },
    legend: { orientation: 'h', y: -0.25 },
  }

  return (
    <ChartErrorBoundary chartName="NetFlowChart">
      <Plot
        data={traces}
        layout={layout as any}
        config={plotConfig}
        style={{ width: '100%', height: '220px' }}
        useResizeHandler
      />
    </ChartErrorBoundary>
  )
}
