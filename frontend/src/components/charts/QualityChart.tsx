import { ChartErrorBoundary } from '../ui/ChartErrorBoundary'
import Plot from 'react-plotly.js'
import { darkLayout, plotConfig, COLORS } from './plotConfig'

interface QualityPoint {
  week: string
  total: number
  bugs: number
  quality_pct: number
}

interface Props {
  data: QualityPoint[]
}

const TARGET_PCT = 80

export default function QualityChart({ data }: Props) {
  if (!data?.length) {
    return (
      <div className="h-48 flex items-center justify-center text-muted text-sm">
        No data
      </div>
    )
  }

  const weeks = data.map(d => d.week)
  const pctValues = data.map(d => d.quality_pct)
  const bugCounts = data.map(d => d.bugs)

  const pointColors = pctValues.map(v => {
    if (v >= TARGET_PCT) return COLORS.success
    if (v >= TARGET_PCT * 0.75) return COLORS.warning
    return COLORS.danger
  })

  const traces: Plotly.Data[] = [
    {
      type: 'bar',
      name: 'Bugs / Defects',
      x: weeks,
      y: bugCounts,
      marker: { color: '#ef4444', opacity: 0.55 },
      yaxis: 'y2',
    },
    {
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Quality %',
      x: weeks,
      y: pctValues,
      line: { color: COLORS.success, width: 2 },
      marker: { size: 6, color: pointColors },
    },
    // Target reference line
    {
      type: 'scatter',
      mode: 'lines',
      name: `Target (${TARGET_PCT}%)`,
      x: [weeks[0], weeks[weeks.length - 1]],
      y: [TARGET_PCT, TARGET_PCT],
      line: { color: COLORS.warning, dash: 'dot', width: 1 },
      opacity: 0.7,
    },
  ]

  // Linear trendline on quality_pct (least squares)
  const n = pctValues.length
  if (n > 1) {
    const xIdx = pctValues.map((_, i) => i)
    const sumX  = xIdx.reduce((a, b) => a + b, 0)
    const sumY  = pctValues.reduce((a, b) => a + b, 0)
    const sumXY = xIdx.reduce((acc, i) => acc + i * pctValues[i], 0)
    const sumX2 = xIdx.reduce((acc, i) => acc + i * i, 0)
    const slope     = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX)
    const intercept = (sumY - slope * sumX) / n

    traces.push({
      type: 'scatter',
      mode: 'lines',
      name: 'Trend',
      x: weeks,
      y: xIdx.map(i => Math.max(0, Math.min(100, slope * i + intercept))),
      line: { color: COLORS.purple, dash: 'dash', width: 2 },
      opacity: 0.8,
    })
  }

  const layout: Partial<Plotly.Layout> = {
    ...darkLayout,
    yaxis: {
      ...darkLayout.yaxis,
      title: { text: 'Quality %' } as any,
      range: [0, 105],
      ticksuffix: '%',
      tickfont: { size: 10 },
    },
    yaxis2: {
      overlaying: 'y' as const,
      side: 'right' as const,
      title: { text: 'Bugs' } as any,
      tickfont: { size: 10, color: '#ef4444' },
      showgrid: false,
    },
    legend: { orientation: 'h', y: -0.25 },
  }

  return (
    <ChartErrorBoundary chartName="QualityChart">
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
