import { useNavigate } from 'react-router-dom'
import { useFilterStore } from '../store/filterStore'
import { useMetricsSummary, useThroughput, useCycleTime, useNetFlow, useQualityRate } from '../api/hooks/useMetrics'
import { useProjects } from '../api/hooks/useProjects'
import KpiCard from '../components/ui/KpiCard'
import AlertBanner from '../components/ui/AlertBanner'
import EmptyState from '../components/ui/EmptyState'
import ThroughputChart from '../components/charts/ThroughputChart'
import TimeScatterChart from '../components/charts/TimeScatterChart'
import NetFlowChart from '../components/charts/NetFlowChart'
import QualityChart from '../components/charts/QualityChart'
import { ChartSkeleton } from '../components/ui/LoadingSkeleton'

export default function Dashboard() {
  const navigate = useNavigate()
  const { activeProjectId, weeks, itemType } = useFilterStore()
  const { data: projects = [] } = useProjects()

  const { data: summary, isLoading } = useMetricsSummary(activeProjectId, weeks, itemType)
  const { data: throughputData = [] } = useThroughput(activeProjectId, weeks, itemType)
  const { data: cycleData } = useCycleTime(activeProjectId, weeks, itemType)
  const { data: netFlowData = [] } = useNetFlow(activeProjectId, weeks, itemType)
  const { data: qualityData = [] } = useQualityRate(activeProjectId, weeks, itemType)

  if (!activeProjectId || projects.length === 0) {
    return (
      <EmptyState
        icon="🌀"
        title="Welcome to Oannes"
        description="Connect your first project to start tracking flow metrics using the Troy Magennis methodology."
        action={{ label: '+ Connect a project', onClick: () => navigate('/projects') }}
      />
    )
  }

  return (
    <div className="space-y-5">
      {(summary?.aging_wip_alerts ?? 0) > 0 && (
        <AlertBanner action={{ label: 'View Aging WIP', onClick: () => navigate('/aging-wip') }}>
          <strong>{summary!.aging_wip_alerts} item{summary!.aging_wip_alerts > 1 ? 's' : ''}</strong> aging beyond the 85th percentile cycle time.
        </AlertBanner>
      )}

      {/* KPI grid */}
      <div className="grid grid-cols-4 gap-4">
        <KpiCard
          label="Throughput"
          value={summary ? `${summary.throughput_avg.toFixed(1)}` : '—'}
          sub="items / week (avg)"
          trend={summary ? { label: `${summary.throughput_trend_pct >= 0 ? '↑' : '↓'} ${Math.abs(summary.throughput_trend_pct).toFixed(0)}% vs prev period`, positive: summary.throughput_trend_pct >= 0 } : undefined}
          accentColor="#6366f1"
        />
        <KpiCard
          label="Cycle Time (85th pct)"
          value={summary?.cycle_time_85th != null ? `${summary.cycle_time_85th.toFixed(0)}d` : '—'}
          sub={summary ? `50th: ${summary.cycle_time_50th?.toFixed(0) ?? '—'}d · 95th: ${summary.cycle_time_95th?.toFixed(0) ?? '—'}d` : ''}
          accentColor="#22c55e"
        />
        <KpiCard
          label="Current WIP"
          value={summary?.current_wip ?? '—'}
          sub="items in flight"
          accentColor="#f59e0b"
        />
        <KpiCard
          label="Flow Efficiency"
          value={summary?.flow_efficiency != null ? `${(summary.flow_efficiency * 100).toFixed(0)}%` : '—'}
          sub="active / total time"
          accentColor="#a78bfa"
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-surface border border-border rounded-xl p-5">
          <div className="flex justify-between items-start mb-4">
            <div>
              <div className="text-sm font-bold">Throughput</div>
              <div className="text-xs text-muted mt-0.5">Items completed per week</div>
            </div>
            <span className="text-[10px] font-semibold bg-primary/15 text-primary px-2 py-1 rounded-full">{weeks} wks</span>
          </div>
          {isLoading ? <ChartSkeleton /> : <ThroughputChart data={throughputData} weeks={weeks} />}
          {summary && (
            <div className="mt-3 px-3 py-2 bg-surface2 rounded-lg text-xs text-muted2 border-l-2 border-primary">
              💡 Throughput trending {summary.throughput_trend_pct >= 0 ? 'up' : 'down'} — avg <strong className="text-text">{summary.throughput_avg.toFixed(1)} items/week</strong> over the last {weeks} weeks.
            </div>
          )}
        </div>

        <div className="bg-surface border border-border rounded-xl p-5">
          <div className="flex justify-between items-start mb-4">
            <div>
              <div className="text-sm font-bold">Cycle Time</div>
              <div className="text-xs text-muted mt-0.5">Days per item, start → done</div>
            </div>
            {summary?.cycle_time_85th && (
              <span className="text-[10px] font-semibold bg-warning/15 text-warning px-2 py-1 rounded-full">85th: {summary.cycle_time_85th.toFixed(0)}d</span>
            )}
          </div>
          {isLoading ? <ChartSkeleton /> : (
            <TimeScatterChart
              data={cycleData?.data ?? []}
              p50={summary?.cycle_time_50th}
              p85={summary?.cycle_time_85th}
              p95={summary?.cycle_time_95th}
              yField="cycle_time_days"
              yLabel="Cycle Time"
            />
          )}
          {summary?.cycle_time_85th && (
            <div className="mt-3 px-3 py-2 bg-surface2 rounded-lg text-xs text-muted2 border-l-2 border-primary">
              💡 Commit to <strong className="text-text">{summary.cycle_time_85th.toFixed(0)} days</strong> and deliver on time <strong className="text-text">85%</strong> of the time.
            </div>
          )}
        </div>
      </div>

      {/* Net Flow chart — full width */}
      <div className="bg-surface border border-border rounded-xl p-5">
        <div className="flex justify-between items-start mb-4">
          <div>
            <div className="text-sm font-bold">Net Flow</div>
            <div className="text-xs text-muted mt-0.5">Weekly arrivals vs completions — positive net means the team is shipping faster than work arrives</div>
          </div>
          <span className="text-[10px] font-semibold bg-primary/15 text-primary px-2 py-1 rounded-full">{weeks} wks</span>
        </div>
        {isLoading ? <ChartSkeleton /> : <NetFlowChart data={netFlowData} />}
        <div className="mt-3 px-3 py-2 bg-surface2 rounded-lg text-xs text-muted2 border-l-2 border-warning">
          💡 A consistently positive net flow means the team is reducing WIP. Negative weeks signal backlog growth.
        </div>
      </div>

      {/* Quality chart — full width */}
      <div className="bg-surface border border-border rounded-xl p-5">
        <div className="flex justify-between items-start mb-4">
          <div>
            <div className="text-sm font-bold">Quality Rate</div>
            <div className="text-xs text-muted mt-0.5">% of completed items that are NOT bugs or defects per week</div>
          </div>
          <span className="text-[10px] font-semibold bg-success/15 text-success px-2 py-1 rounded-full">{weeks} wks</span>
        </div>
        {isLoading ? <ChartSkeleton /> : <QualityChart data={qualityData} />}
        <div className="mt-3 px-3 py-2 bg-surface2 rounded-lg text-xs text-muted2 border-l-2 border-success">
          💡 A high quality rate (&gt;80%) indicates the team spends most of its capacity on new value rather than rework. Declining trend is an early warning signal.
        </div>
      </div>
    </div>
  )
}
