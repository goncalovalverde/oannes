import { useState } from 'react'
import { useFilterStore } from '../store/filterStore'
import { useCycleTime, useItemTypes } from '../api/hooks/useMetrics'
import TimeScatterChart from '../components/charts/TimeScatterChart'
import TimeHistogram from '../components/charts/TimeHistogram'
import { ChartSkeleton } from '../components/ui/LoadingSkeleton'
import EmptyState from '../components/ui/EmptyState'

export default function CycleTime() {
  const { activeProjectId, weeks, itemType: filterItemType } = useFilterStore()
  const { data, isLoading } = useCycleTime(activeProjectId, weeks, filterItemType)
  const { data: availableTypes = [] } = useItemTypes(activeProjectId)
  
  // Local state for multi-select - initialize with all available types
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(() => 
    new Set(availableTypes)
  )

  if (!activeProjectId) return <EmptyState icon="⏱" title="No project selected" description="Select a project from the sidebar." />

  // New ResponseEnvelope format: data.stats contains percentiles, data.data contains items
  const stats = data?.stats
  const allScatter = data?.data ?? []
  
  // Filter scatter data based on selected types
  const scatter = allScatter.filter((item: any) => selectedTypes.has(item.item_type))

  const toggleType = (type: string) => {
    const newSelected = new Set(selectedTypes)
    if (newSelected.has(type)) {
      newSelected.delete(type)
    } else {
      newSelected.add(type)
    }
    setSelectedTypes(newSelected)
  }

  if (!isLoading && allScatter.length === 0) {
    return (
      <EmptyState 
        icon="⏱" 
        title="No data available" 
        description={`No cycle time data found for the last ${weeks} weeks. Try increasing the time window in the filter, or ensure data has been synced.`}
      />
    )
  }

  return (
    <div className="space-y-5">
      {/* Percentile cards */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: '50th Percentile', value: stats?.p50 != null ? `${stats.p50.toFixed(1)}d` : '—', color: '#22c55e', desc: 'Half of items complete faster than this' },
          { label: '85th Percentile', value: stats?.p85 != null ? `${stats.p85.toFixed(1)}d` : '—', color: '#f59e0b', desc: 'Safe commitment date (85% confidence)' },
          { label: '95th Percentile', value: stats?.p95 != null ? `${stats.p95.toFixed(1)}d` : '—', color: '#ef4444', desc: 'Near-guaranteed completion time' },
        ].map(({ label, value, color, desc }) => (
          <div key={label} className="bg-surface border border-border rounded-xl p-4 relative overflow-hidden">
            <div className="absolute top-0 left-0 right-0 h-[3px] rounded-t-xl" style={{ background: color }} />
            <div className="text-[11px] font-semibold text-muted uppercase tracking-widest mb-1">{label}</div>
            <div className="text-2xl font-extrabold" style={{ color }}>{value}</div>
            <div className="text-xs text-muted2 mt-1">{desc}</div>
          </div>
        ))}
      </div>

      {/* Issue type filter */}
      {availableTypes.length > 1 && (
        <div className="bg-surface border border-border rounded-xl p-4">
          <div className="text-xs font-semibold text-muted uppercase tracking-widest mb-3">Filter by Issue Type</div>
          <div className="flex flex-wrap gap-2">
            {availableTypes.map(type => (
              <button
                key={type}
                onClick={() => toggleType(type)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                  selectedTypes.has(type)
                    ? 'bg-primary text-white'
                    : 'bg-surface2 text-muted hover:bg-border'
                }`}
              >
                {type}
              </button>
            ))}
          </div>
          {selectedTypes.size > 0 && (
            <div className="text-xs text-muted2 mt-2">
              Showing {scatter.length} of {allScatter.length} items
            </div>
          )}
        </div>
      )}

      {/* Scatterplot */}
      <div className="bg-surface border border-border rounded-xl p-5">
        <div className="text-sm font-bold mb-1">Cycle Time Scatterplot</div>
        <div className="text-xs text-muted mb-4">Days from work start to done, per item — dashed lines are percentiles</div>
        {isLoading ? <ChartSkeleton /> : (
          <TimeScatterChart data={scatter} p50={stats?.p50} p85={stats?.p85} p95={stats?.p95} yField="cycle_time_days" yLabel="Cycle Time" />
        )}
      </div>

      {/* Histogram */}
      <div className="bg-surface border border-border rounded-xl p-5">
        <div className="text-sm font-bold mb-1">Distribution</div>
        <div className="text-xs text-muted mb-4">How often does each cycle time occur?</div>
        {isLoading ? <ChartSkeleton /> : (
          <TimeHistogram data={scatter} field="cycle_time_days" p50={stats?.p50} p85={stats?.p85} p95={stats?.p95} />
        )}
      </div>

      {stats?.p85 && (
        <div className="px-4 py-3 bg-surface2 border border-border rounded-xl text-sm text-muted2">
          💡 <strong className="text-text">Commit to {stats.p85.toFixed(0)} days</strong> when a stakeholder asks "when will this be done?" — your team delivers within that time <strong className="text-text">85% of the time</strong>, based on the last {weeks} weeks of data.
        </div>
      )}
    </div>
  )
}
