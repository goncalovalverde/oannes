import { ChartErrorBoundary } from '../ui/ChartErrorBoundary'
import Plot from 'react-plotly.js'
import { darkLayout, plotConfig, COLORS } from './plotConfig'
import type { ScatterPoint } from '../../types'

interface Props {
  data: ScatterPoint[]
  field: 'cycle_time_days' | 'lead_time_days'
  p50?: number | null
  p85?: number | null
  p95?: number | null
}

export default function TimeHistogram({ data, field, p50, p85, p95 }: Props) {
  if (!data?.length) return <div className="h-40 flex items-center justify-center text-muted text-sm">No data</div>

  const values = data.map(d => d[field] ?? 0).filter(v => v > 0)

  const traces: Plotly.Data[] = [{
    type: 'histogram', x: values, name: 'Frequency',
    marker: { color: COLORS.primary, opacity: 0.8 },
    nbinsx: 20,
    hovertemplate: '%{x:.1f} days: %{y} items<extra></extra>',
  } as any]

  const shapes: any[] = []
  const annotations: any[] = []
  const pctLines = [
    { val: p50, color: COLORS.success, label: '50th' },
    { val: p85, color: COLORS.warning, label: '85th' },
    { val: p95, color: COLORS.danger,  label: '95th' },
  ]
  pctLines.forEach(({ val, color, label }) => {
    if (val != null) {
      shapes.push({ type: 'line', x0: val, x1: val, y0: 0, y1: 1, yref: 'paper', line: { color, dash: 'dash', width: 1.5 } })
      annotations.push({ x: val, y: 1, yref: 'paper', text: label, showarrow: false, font: { color, size: 10 }, yanchor: 'bottom' })
    }
  })

  return (
    <ChartErrorBoundary chartName="TimeHistogram">
      <Plot
        data={traces}
        layout={{
          ...darkLayout,
          shapes,
          annotations,
          bargap: 0.05,
          xaxis: { type: 'linear', title: 'Days' },
        } as any}
        config={plotConfig}
        style={{ width: '100%', height: '190px' }}
        useResizeHandler
      />
    </ChartErrorBoundary>
  )
}
