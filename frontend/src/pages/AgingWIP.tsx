import { useNavigate } from 'react-router-dom'
import { useFilterStore } from '../store/filterStore'
import { useAgingWip, useMetricsSummary } from '../api/hooks/useMetrics'
import AgingWIPChart from '../components/charts/AgingWIPChart'
import { ChartSkeleton } from '../components/ui/LoadingSkeleton'
import EmptyState from '../components/ui/EmptyState'
import clsx from 'clsx'

export default function AgingWIP() {
  const { activeProjectId, weeks, itemType } = useFilterStore()
  const { data: response, isLoading } = useAgingWip(activeProjectId)
  const { data: summary } = useMetricsSummary(activeProjectId, weeks, itemType)

  if (!activeProjectId) return <EmptyState icon="⧗" title="No project selected" description="Select a project from the sidebar." />

  // response is MetricResponse { data: [...MetricDataPoint], stats: {...} }
  const rawData = response?.data ?? []
  
  // Transform API data to AgingItem format
  // API returns: { date, value (age_days), by_type: { item_key, item_type, stage, is_over_85th } }
  // Page expects: { item_key, item_type, stage, age_days, is_over_85th, started_at }
  const data = rawData.map((item: any) => ({
    item_key: item.by_type?.item_key || '',
    item_type: item.by_type?.item_type || 'Unknown',
    stage: item.by_type?.stage || 'Unknown',
    age_days: item.value,
    is_over_85th: item.by_type?.is_over_85th || false,
    started_at: null,
    item_url: item.by_type?.item_url || null,
  }))

  const atRiskCount = data.filter(d => d.is_over_85th).length

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-surface border border-border rounded-xl p-4">
          <div className="text-[11px] font-semibold text-muted uppercase tracking-widest mb-1">In Flight</div>
          <div className="text-3xl font-extrabold">{data.length}</div>
        </div>
        <div className="bg-surface border border-border rounded-xl p-4">
          <div className="text-[11px] font-semibold text-muted uppercase tracking-widest mb-1">At Risk</div>
          <div className="text-3xl font-extrabold text-danger">{atRiskCount}</div>
        </div>
        <div className="bg-surface border border-border rounded-xl p-4">
          <div className="text-[11px] font-semibold text-muted uppercase tracking-widest mb-1">85th pct CT</div>
          <div className="text-3xl font-extrabold">{summary?.cycle_time_85th != null ? `${summary.cycle_time_85th.toFixed(0)}d` : '—'}</div>
        </div>
      </div>

      <div className="bg-surface border border-border rounded-xl p-5">
        <div className="text-sm font-bold mb-1">Aging WIP Distribution</div>
        <div className="text-xs text-muted mb-4">Distribution of in-flight items by age. Dashed line = 85th percentile cycle time.</div>
        {isLoading ? <ChartSkeleton /> : <AgingWIPChart key={data.length > 0 ? 'has-data' : 'empty'} data={data} p85={summary?.cycle_time_85th} />}
      </div>

      {/* Table */}
      {data.length > 0 && (
        <div className="bg-surface border border-border rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-[11px] font-semibold text-muted uppercase tracking-widest">
                <th className="text-left px-4 py-3">Item</th>
                <th className="text-left px-4 py-3">Type</th>
                <th className="text-left px-4 py-3">Stage</th>
                <th className="text-right px-4 py-3">Age (days)</th>
                <th className="text-left px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.map((item, i) => (
                <tr key={i} className="border-b border-border/50 hover:bg-surface2 transition-colors">
                  <td className="px-4 py-2.5 font-mono text-xs">
                    {item.item_url
                      ? <a href={item.item_url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">{item.item_key}</a>
                      : <span className="text-primary">{item.item_key}</span>
                    }
                  </td>
                  <td className="px-4 py-2.5 text-muted2">{item.item_type}</td>
                  <td className="px-4 py-2.5 text-muted2">{item.stage}</td>
                  <td className="px-4 py-2.5 text-right font-semibold">{item.age_days}</td>
                  <td className={clsx('px-4 py-2.5 text-xs font-semibold', item.is_over_85th ? 'text-danger' : 'text-success')}>
                    {item.is_over_85th ? 'At risk' : 'On track'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="px-4 py-3 bg-surface2 border border-border rounded-xl text-sm text-muted2">
        💡 Items in <span className="text-danger font-semibold">red</span> have exceeded the 85th percentile cycle time — they deserve immediate attention. Each day they stay open increases uncertainty for the whole team.
      </div>
    </div>
  )
}
