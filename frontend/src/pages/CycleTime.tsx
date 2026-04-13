import { useFilterStore } from '../store/filterStore'
import { useCycleTime } from '../api/hooks/useMetrics'
import TimeScatterChart from '../components/charts/TimeScatterChart'
import TimeHistogram from '../components/charts/TimeHistogram'
import { ChartSkeleton } from '../components/ui/LoadingSkeleton'
import EmptyState from '../components/ui/EmptyState'

export default function CycleTime() {
  const { activeProjectId, weeks, itemType } = useFilterStore()
  const { data, isLoading } = useCycleTime(activeProjectId, weeks, itemType)

  if (!activeProjectId) return <EmptyState icon="⏱" title="No project selected" description="Select a project from the sidebar." />

  const pcts = data?.percentiles
  const scatter = data?.data ?? []

  return (
    <div className="space-y-5">
      {/* Percentile cards */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: '50th Percentile', value: pcts?.p50 != null ? `${pcts.p50.toFixed(1)}d` : '—', color: '#22c55e', desc: 'Half of items complete faster than this' },
          { label: '85th Percentile', value: pcts?.p85 != null ? `${pcts.p85.toFixed(1)}d` : '—', color: '#f59e0b', desc: 'Safe commitment date (85% confidence)' },
          { label: '95th Percentile', value: pcts?.p95 != null ? `${pcts.p95.toFixed(1)}d` : '—', color: '#ef4444', desc: 'Near-guaranteed completion time' },
        ].map(({ label, value, color, desc }) => (
          <div key={label} className="bg-surface border border-border rounded-xl p-4 relative overflow-hidden">
            <div className="absolute top-0 left-0 right-0 h-[3px] rounded-t-xl" style={{ background: color }} />
            <div className="text-[11px] font-semibold text-muted uppercase tracking-widest mb-1">{label}</div>
            <div className="text-2xl font-extrabold" style={{ color }}>{value}</div>
            <div className="text-xs text-muted2 mt-1">{desc}</div>
          </div>
        ))}
      </div>

      {/* Scatterplot */}
      <div className="bg-surface border border-border rounded-xl p-5">
        <div className="text-sm font-bold mb-1">Cycle Time Scatterplot</div>
        <div className="text-xs text-muted mb-4">Days from work start to done, per item — dashed lines are percentiles</div>
        {isLoading ? <ChartSkeleton /> : (
          <TimeScatterChart data={scatter} p50={pcts?.p50} p85={pcts?.p85} p95={pcts?.p95} yField="cycle_time_days" yLabel="Cycle Time" />
        )}
      </div>

      {/* Histogram */}
      <div className="bg-surface border border-border rounded-xl p-5">
        <div className="text-sm font-bold mb-1">Distribution</div>
        <div className="text-xs text-muted mb-4">How often does each cycle time occur?</div>
        {isLoading ? <ChartSkeleton /> : (
          <TimeHistogram data={scatter} field="cycle_time_days" p50={pcts?.p50} p85={pcts?.p85} p95={pcts?.p95} />
        )}
      </div>

      {pcts?.p85 && (
        <div className="px-4 py-3 bg-surface2 border border-border rounded-xl text-sm text-muted2">
          💡 <strong className="text-text">Commit to {pcts.p85.toFixed(0)} days</strong> when a stakeholder asks "when will this be done?" — your team delivers within that time <strong className="text-text">85% of the time</strong>, based on the last {weeks} weeks of data.
        </div>
      )}
    </div>
  )
}
