import { ChartErrorBoundary } from '../ui/ChartErrorBoundary'
import Plot from './Plot'
import { darkLayout, plotConfig, COLORS } from './plotConfig'

interface Props {
  data: number[]
  p50?: number | null
  p85?: number | null
  p95?: number | null
}

export default function ThroughputHistogram({ data, p50, p85, p95 }: Props) {
  if (!data?.length) return <div className="h-40 flex items-center justify-center text-muted text-sm">No data</div>

  const values = data.filter(v => v > 0)
  if (!values.length) return <div className="h-40 flex items-center justify-center text-muted text-sm">No data</div>

  const traces: Plotly.Data[] = [{
    type: 'histogram',
    x: values,
    name: 'Frequency',
    marker: { color: COLORS.primary, opacity: 0.8 },
    nbinsx: 15,
    hovertemplate: '%{x} items: %{y} periods<extra></extra>',
  } as any]

  const shapes: any[] = []
  const annotations: any[] = []

  const lines = [
    { value: p50, color: COLORS.success, label: 'p50' },
    { value: p85, color: COLORS.warning, label: 'p85' },
    { value: p95, color: COLORS.danger,  label: 'p95' },
  ]
  for (const { value, color, label } of lines) {
    if (value != null) {
      shapes.push({ type: 'line', x0: value, x1: value, y0: 0, y1: 1, yref: 'paper', line: { color, dash: 'dash', width: 1.5 } })
      annotations.push({ x: value, y: 1, yref: 'paper', text: label, showarrow: false, font: { color, size: 10 }, yanchor: 'bottom' })
    }
  }

  return (
    <ChartErrorBoundary chartName="ThroughputHistogram">
      <Plot
        data={traces}
        layout={{
          ...darkLayout,
          shapes,
          annotations,
          bargap: 0.05,
          xaxis: { ...darkLayout.xaxis, type: 'linear', title: { text: 'Items completed', font: { color: '#64748b', size: 11 } } },
        } as any}
        config={plotConfig}
        style={{ width: '100%', height: '190px' }}
        useResizeHandler
      />
    </ChartErrorBoundary>
  )
}
