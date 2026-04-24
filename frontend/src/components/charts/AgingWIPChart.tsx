import { ChartErrorBoundary } from '../ui/ChartErrorBoundary'
import Plot from './Plot'
import { darkLayout, plotConfig, COLORS } from './plotConfig'
import type { AgingItem } from '../../types'

interface Props { data: AgingItem[]; p85?: number | null }

export default function AgingWIPChart({ data, p85 }: Props) {
  if (!data?.length) return <div className="h-48 flex items-center justify-center text-muted text-sm">No aging WIP data</div>

  const onTrack = data.filter(d => !d.is_over_85th).map(d => d.age_days)
  const atRisk  = data.filter(d =>  d.is_over_85th).map(d => d.age_days)

  const traces: Plotly.Data[] = [
    {
      type: 'histogram',
      x: onTrack,
      name: 'On track',
      marker: { color: COLORS.primary },
      opacity: 0.85,
      hovertemplate: '%{x} days: %{y} items<extra>On track</extra>',
    },
    {
      type: 'histogram',
      x: atRisk,
      name: 'At risk',
      marker: { color: COLORS.danger },
      opacity: 0.85,
      hovertemplate: '%{x} days: %{y} items<extra>At risk</extra>',
    },
  ]

  const shapes: any[] = p85 != null ? [{
    type: 'line', x0: p85, x1: p85, y0: 0, y1: 1, yref: 'paper',
    line: { color: COLORS.warning, dash: 'dash', width: 1.5 },
  }] : []

  const annotations: any[] = p85 != null ? [{
    x: p85, y: 1, yref: 'paper', xanchor: 'left', yanchor: 'top',
    text: `85th pct: ${Math.round(p85)}d`,
    showarrow: false,
    font: { color: COLORS.warning, size: 11 },
  }] : []

  return (
    <ChartErrorBoundary chartName="AgingWIPChart">
      <Plot
        data={traces}
        layout={{
          ...darkLayout,
          barmode: 'stack',
          shapes,
          annotations,
          xaxis: { ...darkLayout.xaxis, type: 'linear', title: { text: 'Age (days)', font: { color: '#64748b', size: 11 } } },
          yaxis: { ...darkLayout.yaxis, title: { text: 'Items', font: { color: '#64748b', size: 11 } } },
          height: 300,
        } as any}
        config={plotConfig}
        style={{ width: '100%' }}
        useResizeHandler
      />
    </ChartErrorBoundary>
  )
}
