import { useFilterStore } from '../store/filterStore'
import { useCfd } from '../api/hooks/useMetrics'
import CFDChart from '../components/charts/CFDChart'
import { ChartSkeleton } from '../components/ui/LoadingSkeleton'
import EmptyState from '../components/ui/EmptyState'

export default function CFD() {
  const { activeProjectId } = useFilterStore()
  const { data = [], isLoading } = useCfd(activeProjectId)

  if (!activeProjectId) return <EmptyState icon="∿" title="No project selected" description="Select a project from the sidebar." />

  return (
    <div className="space-y-5">
      <div className="bg-surface border border-border rounded-xl p-5">
        <div className="text-sm font-bold mb-1">Cumulative Flow Diagram</div>
        <div className="text-xs text-muted mb-4">Items accumulated in each stage over time — bands widening indicate bottlenecks</div>
        {isLoading ? <ChartSkeleton /> : <CFDChart data={data} />}
      </div>

      <div className="px-4 py-3 bg-surface2 border border-border rounded-xl text-sm text-muted2">
        💡 A healthy CFD shows <strong className="text-text">parallel bands of consistent width</strong>. A widening band in a stage means work is accumulating there — a bottleneck. A narrowing band means items are skipping that stage.
      </div>
    </div>
  )
}
