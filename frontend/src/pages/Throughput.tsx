import { useFilterStore } from '../store/filterStore'
import { useThroughput, useMetricsSummary } from '../api/hooks/useMetrics'
import ThroughputChart from '../components/charts/ThroughputChart'
import { ChartSkeleton } from '../components/ui/LoadingSkeleton'
import EmptyState from '../components/ui/EmptyState'

export default function Throughput() {
  const { activeProjectId, weeks, itemType, granularity } = useFilterStore()
  const { data, isLoading } = useThroughput(activeProjectId, weeks, itemType, granularity)
  const { data: summary } = useMetricsSummary(activeProjectId, weeks, itemType)

  if (!activeProjectId) return <EmptyState icon="↑" title="No project selected" description="Select a project from the sidebar." />
  
  const rawData = data?.data ?? []
  const stats = data?.stats
  
  if (!isLoading && rawData.length === 0) {
    return (
      <EmptyState 
        icon="↑" 
        title="No data available" 
        description={`No throughput data found for the last ${weeks} weeks. Try increasing the time window in the filter, or ensure data has been synced.`}
      />
    )
  }

  // Transform API data (flat list) to ThroughputChart format (grouped by week with item types)
  // API returns: [{ date: "2023-09-18", value: 1.0, by_type: { Task: 1, Bug: 0 } }]
  // Chart expects: [{ week: "2023-W39", Total: 3, Task: 2, Bug: 1 }]
  const chartData: any[] = rawData.map((item: any) => {
    const base = {
      week: item.date,
      Total: item.value || 0,
    }
    // Spread item types from by_type object if present
    if (item.by_type && typeof item.by_type === 'object') {
      return { ...base, ...item.by_type }
    }
    return base
  })

  const avg = stats?.avg ?? 0
  const trend = stats?.trend_pct ?? 0

  const granularityLabel = granularity === 'biweek' ? 'Bi-weekly' : granularity === 'month' ? 'Monthly' : granularity === 'day' ? 'Daily' : 'Weekly'

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Average', value: `${avg.toFixed(1)}/wk` },
          { label: 'Trend', value: `${trend >= 0 ? '+' : ''}${trend.toFixed(0)}%` },
          { label: 'Data points', value: chartData.length },
        ].map(({ label, value }) => (
          <div key={label} className="bg-surface border border-border rounded-xl p-4">
            <div className="text-[11px] font-semibold text-muted uppercase tracking-widest mb-1">{label}</div>
            <div className="text-2xl font-extrabold">{value}</div>
          </div>
        ))}
      </div>

      <div className="bg-surface border border-border rounded-xl p-5">
        <div className="flex justify-between items-start mb-1">
          <div className="text-sm font-bold">{granularityLabel} Throughput</div>
          <span className="text-[10px] font-semibold bg-primary/15 text-primary px-2 py-1 rounded-full">{granularityLabel}</span>
        </div>
        <div className="text-xs text-muted mb-4">Items completed per {granularity === 'month' ? 'month' : granularity === 'biweek' ? 'two weeks' : granularity === 'day' ? 'day' : 'week'}</div>
        {isLoading ? <ChartSkeleton /> : <ThroughputChart data={chartData} weeks={weeks} />}
        <div className="mt-4 px-3 py-2 bg-surface2 rounded-lg text-xs text-muted2 border-l-2 border-primary">
          💡 Your team completes an average of <strong className="text-text">{avg.toFixed(1)} items per week</strong>.
          The dashed line shows the trend over the selected period.
        </div>
      </div>
    </div>
  )
}
