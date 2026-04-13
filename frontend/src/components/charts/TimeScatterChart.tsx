import { ChartErrorBoundary } from '../ui/ChartErrorBoundary'
import Plot from 'react-plotly.js'
import { darkLayout, plotConfig, COLORS, TYPE_COLORS } from './plotConfig'
import type { ScatterPoint } from '../../types'

interface Props {
  data: ScatterPoint[]
  p50?: number | null
  p85?: number | null
  p95?: number | null
  yField: 'cycle_time_days' | 'lead_time_days'
  yLabel: string
  expanded?: boolean
}

export default function TimeScatterChart({ data, p50, p85, p95, yField, yLabel, expanded = false }: Props) {
  if (!data?.length) return <div className="h-48 flex items-center justify-center text-muted text-sm">No data</div>

  const types = [...new Set(data.map(d => d.item_type))]
  const xDates = data.map(d => d.completed_at)

  const traces: Plotly.Data[] = types.map((t, i) => {
    const subset = data.filter(d => d.item_type === t)
    return {
      type: 'scatter', mode: 'markers', name: t,
      x: subset.map(d => d.completed_at),
      y: subset.map(d => d[yField] ?? 0),
      marker: { color: TYPE_COLORS[i % TYPE_COLORS.length], size: 7, opacity: 0.75 },
      hovertemplate: `%{text}<br>${yLabel}: %{y:.1f}d<extra></extra>`,
      text: subset.map(d => d.item_key),
    }
  })

  // Percentile lines
  const xMin = xDates[0], xMax = xDates[xDates.length - 1]
  const pctLines = [
    { val: p50, color: COLORS.success, label: '50th' },
    { val: p85, color: COLORS.warning, label: '85th' },
    { val: p95, color: COLORS.danger,  label: '95th' },
  ]
  pctLines.forEach(({ val, color, label }) => {
    if (val != null) {
      traces.push({
        type: 'scatter', mode: 'lines', name: label,
        x: [xMin, xMax], y: [val, val],
        line: { color, dash: 'dash', width: 1.5 },
        hovertemplate: `${label}: ${val.toFixed(1)}d<extra></extra>`,
      })
    }
  })

  return (
    <ChartErrorBoundary chartName="TimeScatterChart">
      <Plot
        data={traces}
        layout={{ ...darkLayout, yaxis: { ...darkLayout.yaxis, title: { text: 'Days', font: { color: '#64748b', size: 11 } } } } as any}
        config={plotConfig}
        style={{ width: '100%', height: expanded ? '400px' : '220px' }}
        useResizeHandler
      />
    </ChartErrorBoundary>
  )
}
