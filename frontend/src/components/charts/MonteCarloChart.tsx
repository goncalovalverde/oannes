import { ChartErrorBoundary } from '../ui/ChartErrorBoundary'
import Plot from './Plot'
import { darkLayout, plotConfig, COLORS } from './plotConfig'
import type { MonteCarloResult } from '../../types'

interface Props { result: MonteCarloResult }

export default function MonteCarloChart({ result }: Props) {
  const isWhenDone = result.mode === 'when_done'
  const xField = isWhenDone ? 'weeks' : 'items'
  const xLabel = isWhenDone ? 'Weeks to complete' : 'Items completed'

  const traces: Plotly.Data[] = [{
    type: 'bar',
    x: result.histogram.map(d => (d as any)[xField]),
    y: result.histogram.map(d => d.probability),
    marker: { color: COLORS.primary, opacity: 0.8 },
    name: 'Probability',
    hovertemplate: `${xLabel}: %{x}<br>Probability: %{y:.1%}<extra></extra>`,
  }]

  // Percentile markers — only for how_many mode (when_done percentiles are dates, not week numbers)
  const pcts = result.percentiles
  if (pcts && !isWhenDone) {
    const markers = [
      { key: '50', color: COLORS.success, label: '50%' },
      { key: '85', color: COLORS.warning, label: '85%' },
      { key: '95', color: COLORS.danger,  label: '95%' },
    ]
    markers.forEach(({ key, color, label }) => {
      const val = pcts[key]
      if (val != null && typeof val === 'number') {
        traces.push({
          type: 'scatter', mode: 'lines', name: label,
          x: [val, val], y: [0, Math.max(...result.histogram.map(d => d.probability))],
          line: { color, dash: 'dash', width: 2 },
        })
      }
    })
  }

  return (
    <ChartErrorBoundary chartName="MonteCarloChart">
      <Plot
        data={traces}
        layout={{
          ...darkLayout,
          xaxis: { ...darkLayout.xaxis, title: { text: xLabel, font: { color: '#64748b', size: 11 } } },
          yaxis: { ...darkLayout.yaxis, title: { text: 'Probability', font: { color: '#64748b', size: 11 } }, tickformat: '.0%' },
        } as any}
        config={plotConfig}
        style={{ width: '100%', height: '260px' }}
        useResizeHandler
      />
    </ChartErrorBoundary>
  )
}
