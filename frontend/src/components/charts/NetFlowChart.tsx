import { ChartErrorBoundary } from '../ui/ChartErrorBoundary'
import Plot from 'react-plotly.js'
import { darkLayout, plotConfig, COLORS } from './plotConfig'

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
  const netValues = data.map(d => d.net)

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
      y: netValues,
      yaxis: 'y2',
      line: { color: '#f59e0b', width: 2 },
      marker: { size: 5, color: netValues.map(v => (v >= 0 ? '#22c55e' : '#ef4444')) },
    },
  ]

  // Linear trendline on net flow values (least squares)
  const n = netValues.length
  if (n > 1) {
    const xIdx = netValues.map((_, i) => i)
    const sumX  = xIdx.reduce((a, b) => a + b, 0)
    const sumY  = netValues.reduce((a, b) => a + b, 0)
    const sumXY = xIdx.reduce((acc, i) => acc + i * netValues[i], 0)
    const sumX2 = xIdx.reduce((acc, i) => acc + i * i, 0)
    const slope     = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX)
    const intercept = (sumY - slope * sumX) / n

    traces.push({
      type: 'scatter',
      mode: 'lines',
      name: 'Net Trend',
      x: weeks,
      y: xIdx.map(i => slope * i + intercept),
      yaxis: 'y2',
      line: { color: COLORS.purple, dash: 'dash', width: 2 },
      opacity: 0.8,
    })
  }

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
