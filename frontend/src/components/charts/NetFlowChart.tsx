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
  expanded?: boolean
}

export default function NetFlowChart({ data, expanded = false }: Props) {
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
      name: 'Net Flow',
      x: weeks,
      y: netValues,
      // Colour each bar: green when completions > arrivals, red otherwise
      marker: {
        color: netValues.map(v => (v >= 0 ? COLORS.success : COLORS.danger)),
        opacity: 0.8,
      },
      hovertemplate: '%{x}<br>Net: %{y}<extra></extra>',
    },
  ]

  // Linear trendline (least squares)
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
      name: 'Trend',
      x: weeks,
      y: xIdx.map(i => slope * i + intercept),
      line: { color: COLORS.purple, dash: 'dash', width: 2 },
      opacity: 0.85,
    })
  }

  const layout: Partial<Plotly.Layout> = {
    ...darkLayout,
    yaxis: {
      ...darkLayout.yaxis,
      title: { text: 'Net Flow (done − started)' } as any,
      tickfont: { size: 10 },
      zeroline: true,
      zerolinecolor: '#6b7280',
      zerolinewidth: 1,
    },
    legend: { orientation: 'h', y: -0.25 },
  }

  return (
    <ChartErrorBoundary chartName="NetFlowChart">
      <Plot
        data={traces}
        layout={layout as any}
        config={plotConfig}
        style={{ width: '100%', height: expanded ? '400px' : '220px' }}
        useResizeHandler
      />
    </ChartErrorBoundary>
  )
}
