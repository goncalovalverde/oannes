import { ChartErrorBoundary } from '../ui/ChartErrorBoundary'
import Plot from './Plot'
import { darkLayout, plotConfig, COLORS, TYPE_COLORS } from './plotConfig'
import type { ThroughputPoint } from '../../types'

interface Props { data: ThroughputPoint[]; weeks: number }

export default function ThroughputChart({ data, weeks }: Props) {
  if (!data?.length) return <div className="h-48 flex items-center justify-center text-muted text-sm">No data</div>

  const types = Object.keys(data[0]).filter(k => k !== 'week' && k !== 'Total')
  const weeks_x = data.map(d => d.week)

  // Diagnostic — remove once issue is confirmed fixed
  const totals_raw = data.map(d => d.Total ?? 0)
  const maxTotal = Math.max(...totals_raw)
  if (maxTotal > 1000) {
    console.warn('[ThroughputChart] ⚠️ Suspiciously large values detected! maxTotal=', maxTotal, 'first 3 points=', data.slice(0, 3))
  } else {
    console.log('[ThroughputChart] ✅ data OK — n=', data.length, 'maxTotal=', maxTotal)
  }

  const traces: Plotly.Data[] = types.map((t, i) => ({
    type: 'bar',
    name: t,
    x: weeks_x,
    y: data.map(d => d[t] ?? 0),
    marker: { color: TYPE_COLORS[i % TYPE_COLORS.length] },
  }))

  // Trendline on Total (extends beyond data range for proper zoom behavior)
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
    
    // Extend trendline slightly beyond data range for better zoom behavior
    const extendFactor = 0.05
    const minX = -extendFactor * (n - 1)
    const maxX = (n - 1) * (1 + extendFactor)
    const trendlineX = [minX, maxX]
    const trendlineY = trendlineX.map(i => slope * i + intercept)
    
    traces.push({
      type: 'scatter', mode: 'lines', name: 'Trend',
      x: trendlineX.map(i => weeks_x[Math.round(i)] || (i < 0 ? weeks_x[0] : weeks_x[weeks_x.length - 1])),
      y: trendlineY,
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
        style={{ width: '100%', height: '220px' }}
        useResizeHandler
      />
    </ChartErrorBoundary>
  )
}
