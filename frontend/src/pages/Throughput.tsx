import { useFilterStore } from '../store/filterStore'
import { useThroughput, useMetricsSummary } from '../api/hooks/useMetrics'
import ThroughputChart from '../components/charts/ThroughputChart'
import { ChartSkeleton } from '../components/ui/LoadingSkeleton'
import EmptyState from '../components/ui/EmptyState'

export default function Throughput() {
  const { activeProjectId, weeks, itemType } = useFilterStore()
  const { data = [], isLoading } = useThroughput(activeProjectId, weeks, itemType)
  const { data: summary } = useMetricsSummary(activeProjectId, weeks, itemType)

  if (!activeProjectId) return <EmptyState icon="↑" title="No project selected" description="Select a project from the sidebar." />

  const avg = summary?.throughput_avg ?? 0
  const trend = summary?.throughput_trend_pct ?? 0

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Average', value: `${avg.toFixed(1)}/wk` },
          { label: 'Trend', value: `${trend >= 0 ? '+' : ''}${trend.toFixed(0)}%` },
          { label: 'Data points', value: data.length },
        ].map(({ label, value }) => (
          <div key={label} className="bg-surface border border-border rounded-xl p-4">
            <div className="text-[11px] font-semibold text-muted uppercase tracking-widest mb-1">{label}</div>
            <div className="text-2xl font-extrabold">{value}</div>
          </div>
        ))}
      </div>

      <div className="bg-surface border border-border rounded-xl p-5">
        <div className="text-sm font-bold mb-1">Weekly Throughput</div>
        <div className="text-xs text-muted mb-4">Items completed per week, stacked by type</div>
        {isLoading ? <ChartSkeleton /> : <ThroughputChart data={data} weeks={weeks} />}
        <div className="mt-4 px-3 py-2 bg-surface2 rounded-lg text-xs text-muted2 border-l-2 border-primary">
          💡 Your team completes an average of <strong className="text-text">{avg.toFixed(1)} items per week</strong>.
          The dashed line shows the trend over the selected period.
        </div>
      </div>
    </div>
  )
}
