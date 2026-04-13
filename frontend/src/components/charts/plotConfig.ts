export const darkLayout: Partial<Plotly.Layout> = {
  paper_bgcolor: '#13161f',
  plot_bgcolor: '#13161f',
  font: { color: '#e2e8f0', family: 'Inter, system-ui, sans-serif', size: 12 },
  xaxis: { gridcolor: '#252836', linecolor: '#252836', zerolinecolor: '#252836', tickfont: { color: '#64748b' } },
  yaxis: { gridcolor: '#252836', linecolor: '#252836', zerolinecolor: '#252836', tickfont: { color: '#64748b' } },
  margin: { t: 20, r: 20, b: 50, l: 55 },
  legend: { bgcolor: 'transparent', font: { color: '#94a3b8' }, orientation: 'h', y: -0.15 },
  hoverlabel: { bgcolor: '#1c2030', bordercolor: '#2f3347', font: { color: '#e2e8f0' } },
}

export const plotConfig = {
  displayModeBar: false,
  responsive: true,
}

export const COLORS = {
  primary:  '#6366f1',
  success:  '#22c55e',
  warning:  '#f59e0b',
  danger:   '#ef4444',
  purple:   '#a78bfa',
  teal:     '#2dd4bf',
  orange:   '#fb923c',
  pink:     '#f472b6',
}

export const TYPE_COLORS = [
  COLORS.primary, COLORS.teal, COLORS.orange, COLORS.pink,
  COLORS.purple, COLORS.success, COLORS.warning,
]
