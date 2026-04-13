import { useFilterStore } from '../store/filterStore'
import { useLeadTime } from '../api/hooks/useMetrics'
import TimeScatterChart from '../components/charts/TimeScatterChart'
import TimeHistogram from '../components/charts/TimeHistogram'
import { ChartSkeleton } from '../components/ui/LoadingSkeleton'
import EmptyState from '../components/ui/EmptyState'

export default function LeadTime() {
  const { activeProjectId, weeks, itemType } = useFilterStore()
  const { data, isLoading } = useLeadTime(activeProjectId, weeks, itemType)

  if (!activeProjectId) return <EmptyState icon="⤳" title="No project selected" description="Select a project from the sidebar." />

  const pcts = data?.percentiles
  const scatter = data?.data ?? []

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: '50th Percentile', value: pcts?.p50 != null ? `${pcts.p50.toFixed(1)}d` : '—', color: '#22c55e' },
          { label: '85th Percentile', value: pcts?.p85 != null ? `${pcts.p85.toFixed(1)}d` : '—', color: '#f59e0b' },
          { label: '95th Percentile', value: pcts?.p95 != null ? `${pcts.p95.toFixed(1)}d` : '—', color: '#ef4444' },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-surface border border-border rounded-xl p-4 relative overflow-hidden">
            <div className="absolute top-0 left-0 right-0 h-[3px] rounded-t-xl" style={{ background: color }} />
            <div className="text-[11px] font-semibold text-muted uppercase tracking-widest mb-1">{label}</div>
            <div className="text-2xl font-extrabold" style={{ color }}>{value}</div>
          </div>
        ))}
      </div>

      <div className="bg-surface border border-border rounded-xl p-5">
        <div className="text-sm font-bold mb-1">Lead Time Scatterplot</div>
        <div className="text-xs text-muted mb-4">Days from item creation to done — includes wait time before work starts</div>
        {isLoading ? <ChartSkeleton /> : (
          <TimeScatterChart data={scatter} p50={pcts?.p50} p85={pcts?.p85} p95={pcts?.p95} yField="lead_time_days" yLabel="Lead Time" />
        )}
      </div>

      <div className="bg-surface border border-border rounded-xl p-5">
        <div className="text-sm font-bold mb-1">Distribution</div>
        {isLoading ? <ChartSkeleton /> : (
          <TimeHistogram data={scatter} field="lead_time_days" p50={pcts?.p50} p85={pcts?.p85} p95={pcts?.p95} />
        )}
      </div>

      <div className="px-4 py-3 bg-surface2 border border-border rounded-xl text-sm text-muted2">
        💡 Lead time includes time waiting in the backlog. If lead time is much larger than cycle time, your team has a <strong className="text-text">queue problem</strong> — work sits waiting before it's even started.
      </div>
    </div>
  )
}
