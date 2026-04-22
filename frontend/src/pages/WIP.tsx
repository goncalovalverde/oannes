import { useFilterStore } from '../store/filterStore'
import { useWip, useMetricsSummary } from '../api/hooks/useMetrics'
import WIPChart from '../components/charts/WIPChart'
import { ChartSkeleton } from '../components/ui/LoadingSkeleton'
import EmptyState from '../components/ui/EmptyState'

export default function WIP() {
  const { activeProjectId, weeks } = useFilterStore()
  const { data: rawData = [], isLoading } = useWip(activeProjectId, weeks)
  const { data: summary } = useMetricsSummary(activeProjectId, weeks, 'all')

  if (!activeProjectId) return <EmptyState icon="≋" title="No project selected" description="Select a project from the sidebar." />

  // Transform API data to component format
  // API returns: { date, value, by_type: { stage } }
  // Component expects: { date, stage, count }
  const data = rawData.map((item: any) => ({
    date: item.date,
    stage: item.by_type?.stage || 'Unknown',
    count: item.value,
  }))

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-surface border border-border rounded-xl p-4">
          <div className="text-[11px] font-semibold text-muted uppercase tracking-widest mb-1">Current WIP</div>
          <div className="text-3xl font-extrabold">{summary?.current_wip ?? '—'}</div>
          <div className="text-xs text-muted2 mt-1">items currently in flight</div>
        </div>
        <div className="bg-surface border border-border rounded-xl p-4">
          <div className="text-[11px] font-semibold text-muted uppercase tracking-widest mb-1">Flow Efficiency</div>
          <div className="text-3xl font-extrabold">
            {summary?.flow_efficiency != null ? `${(summary.flow_efficiency * 100).toFixed(0)}%` : '—'}
          </div>
          <div className="text-xs text-muted2 mt-1">active vs total time</div>
        </div>
      </div>

      <div className="bg-surface border border-border rounded-xl p-5">
        <div className="text-sm font-bold mb-1">WIP Over Time</div>
        <div className="text-xs text-muted mb-4">Items in each workflow stage, sampled weekly</div>
        {isLoading ? <ChartSkeleton /> : <WIPChart data={data} />}
      </div>

      <div className="px-4 py-3 bg-surface2 border border-border rounded-xl text-sm text-muted2">
        💡 High WIP slows your team down. Little's Law: <em>Cycle Time = WIP ÷ Throughput</em>. To reduce cycle time, reduce WIP. Consider setting explicit WIP limits per stage.
      </div>
    </div>
  )
}
