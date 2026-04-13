import { ChartErrorBoundary } from '../ui/ChartErrorBoundary'
import Plot from 'react-plotly.js'
import { darkLayout, plotConfig, COLORS } from './plotConfig'
import type { AgingItem } from '../../types'

interface Props { data: AgingItem[]; p85?: number | null }

export default function AgingWIPChart({ data, p85 }: Props) {
  if (!data?.length) return <div className="h-48 flex items-center justify-center text-muted text-sm">No aging WIP data</div>

  const sorted = [...data].sort((a, b) => b.age_days - a.age_days).slice(0, 30)
  const colors = sorted.map(d => d.is_over_85th ? COLORS.danger : COLORS.success)

  const traces: Plotly.Data[] = [{
    type: 'bar', orientation: 'h',
    x: sorted.map(d => d.age_days),
    y: sorted.map(d => `${d.item_key} (${d.stage})`),
    marker: { color: colors },
    hovertemplate: '%{y}<br>Age: %{x} days<extra></extra>',
  }]

  const shapes: any[] = p85 != null ? [{
    type: 'line', x0: p85, x1: p85, y0: -0.5, y1: sorted.length - 0.5,
    line: { color: COLORS.warning, dash: 'dash', width: 1.5 },
  }] : []

  return (
    <ChartErrorBoundary chartName="AgingWIPChart">
      <Plot
        data={traces}
        layout={{
          ...darkLayout,
          shapes,
          xaxis: { ...darkLayout.xaxis, title: { text: 'Age (days)', font: { color: '#64748b', size: 11 } } },
          margin: { ...darkLayout.margin, l: 160 },
          height: Math.max(200, sorted.length * 28),
        } as any}
        config={plotConfig}
        style={{ width: '100%' }}
        useResizeHandler
      />
    </ChartErrorBoundary>
  )
}
