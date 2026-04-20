import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useFilterStore } from '../store/filterStore'
import { useMetricsSummary, useThroughput, useNetFlow, useQualityRate, useCycleTimeInterval } from '../api/hooks/useMetrics'
import { useProjects } from '../api/hooks/useProjects'
import KpiCard from '../components/ui/KpiCard'
import AlertBanner from '../components/ui/AlertBanner'
import EmptyState from '../components/ui/EmptyState'
import ThroughputChart from '../components/charts/ThroughputChart'
import NetFlowChart from '../components/charts/NetFlowChart'
import QualityChart from '../components/charts/QualityChart'
import CycleTimeIntervalChart from '../components/charts/CycleTimeIntervalChart'
import { ChartSkeleton } from '../components/ui/LoadingSkeleton'

type ChartId = 'quality' | 'cycle' | 'throughput' | 'netflow'

function ExpandButton({ expanded, onToggle }: { expanded: boolean; onToggle: () => void }) {
  return (
    <button
      onClick={onToggle}
      title={expanded ? 'Collapse' : 'Expand to full row'}
      className="ml-2 p-1 rounded text-muted hover:text-text hover:bg-surface2 transition-colors flex-shrink-0"
      aria-label={expanded ? 'Collapse chart' : 'Expand chart'}
    >
      {expanded
        ? <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M5 10a1 1 0 011-1h8a1 1 0 110 2H6a1 1 0 01-1-1z" clipRule="evenodd"/></svg>
        : <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M3 4a1 1 0 011-1h4a1 1 0 010 2H6.414l2.293 2.293a1 1 0 01-1.414 1.414L5 6.414V8a1 1 0 01-2 0V4zm9 1a1 1 0 010-2h4a1 1 0 011 1v4a1 1 0 01-2 0V6.414l-2.293 2.293a1 1 0 11-1.414-1.414L13.586 5H12zm-9 7a1 1 0 012 0v1.586l2.293-2.293a1 1 0 011.414 1.414L6.414 15H8a1 1 0 010 2H4a1 1 0 01-1-1v-4zm13-1a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 010-2h1.586l-2.293-2.293a1 1 0 011.414-1.414L15 13.586V12a1 1 0 011-1z" clipRule="evenodd"/></svg>
      }
    </button>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { activeProjectId, weeks, itemType, granularity } = useFilterStore()
  const { data: projects = [] } = useProjects()
  const [expanded, setExpanded] = useState<Set<ChartId>>(new Set())

  const { data: summary, isLoading: summaryLoading } = useMetricsSummary(activeProjectId, weeks, itemType)
  const { data: throughputData = [], isFetching: throughputFetching } = useThroughput(activeProjectId, weeks, itemType, granularity)
  const { data: netFlowData = [], isFetching: netFlowFetching } = useNetFlow(activeProjectId, weeks, itemType, granularity)
  const { data: qualityData = [], isFetching: qualityFetching } = useQualityRate(activeProjectId, weeks, itemType, granularity)
  const { data: cycleTimeData = [], isFetching: cycleTimeFetching } = useCycleTimeInterval(activeProjectId, weeks, itemType, granularity)

  const toggle = (id: ChartId) =>
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  const isExpanded = (id: ChartId) => expanded.has(id)
  const colSpan = (id: ChartId) => isExpanded(id) ? 'col-span-2' : ''

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

      {/* Charts — 2×2 grid with per-chart expand */}
      <div className="grid grid-cols-2 gap-4">
        {/* 1 — Quality Rate */}
        <div className={`bg-surface border border-border rounded-xl p-5 ${colSpan('quality')}`}>
          <div className="flex justify-between items-start mb-4">
            <div>
              <div className="text-sm font-bold">Quality Rate</div>
              <div className="text-xs text-muted mt-0.5">% of completed items that are NOT bugs or defects per week</div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-semibold bg-success/15 text-success px-2 py-1 rounded-full">{weeks} wks</span>
              <ExpandButton expanded={isExpanded('quality')} onToggle={() => toggle('quality')} />
            </div>
          </div>
          {qualityFetching ? <ChartSkeleton /> : <QualityChart key={String(isExpanded('quality'))} data={qualityData} />}
          <div className="mt-3 px-3 py-2 bg-surface2 rounded-lg text-xs text-muted2 border-l-2 border-success">
            💡 A high quality rate (&gt;80%) indicates the team spends most of its capacity on new value rather than rework. Declining trend is an early warning signal.
          </div>
        </div>

        {/* 2 — Cycle Time */}
        <div className={`bg-surface border border-border rounded-xl p-5 ${colSpan('cycle')}`}>
          <div className="flex justify-between items-start mb-4">
            <div>
              <div className="text-sm font-bold">Cycle Time</div>
              <div className="text-xs text-muted mt-0.5">Average days per item, start → done</div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-semibold bg-warning/15 text-warning px-2 py-1 rounded-full">{weeks} wks</span>
              <ExpandButton expanded={isExpanded('cycle')} onToggle={() => toggle('cycle')} />
            </div>
          </div>
          {cycleTimeFetching ? <ChartSkeleton /> : <CycleTimeIntervalChart key={String(isExpanded('cycle'))} data={cycleTimeData} />}
          {summary?.cycle_time_85th && (
            <div className="mt-3 px-3 py-2 bg-surface2 rounded-lg text-xs text-muted2 border-l-2 border-primary">
              💡 Commit to <strong className="text-text">{summary.cycle_time_85th.toFixed(0)} days</strong> and deliver on time <strong className="text-text">85%</strong> of the time.
            </div>
          )}
        </div>

        {/* 3 — Throughput */}
        <div className={`bg-surface border border-border rounded-xl p-5 ${colSpan('throughput')}`}>
          <div className="flex justify-between items-start mb-4">
            <div>
              <div className="text-sm font-bold">Throughput</div>
              <div className="text-xs text-muted mt-0.5">Items completed per week</div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-semibold bg-primary/15 text-primary px-2 py-1 rounded-full">{weeks} wks</span>
              <ExpandButton expanded={isExpanded('throughput')} onToggle={() => toggle('throughput')} />
            </div>
          </div>
          {throughputFetching ? <ChartSkeleton /> : <ThroughputChart key={String(isExpanded('throughput'))} data={throughputData} weeks={weeks} />}
          {summary && (
            <div className="mt-3 px-3 py-2 bg-surface2 rounded-lg text-xs text-muted2 border-l-2 border-primary">
              💡 Throughput trending {summary.throughput_trend_pct >= 0 ? 'up' : 'down'} — avg <strong className="text-text">{summary.throughput_avg.toFixed(1)} items/week</strong> over the last {weeks} weeks.
            </div>
          )}
        </div>

        {/* 4 — Net Flow */}
        <div className={`bg-surface border border-border rounded-xl p-5 ${colSpan('netflow')}`}>
          <div className="flex justify-between items-start mb-4">
            <div>
              <div className="text-sm font-bold">Net Flow</div>
              <div className="text-xs text-muted mt-0.5">Done minus started per week — positive means shipping faster than work arrives</div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-semibold bg-primary/15 text-primary px-2 py-1 rounded-full">{weeks} wks</span>
              <ExpandButton expanded={isExpanded('netflow')} onToggle={() => toggle('netflow')} />
            </div>
          </div>
          {netFlowFetching ? <ChartSkeleton /> : <NetFlowChart key={String(isExpanded('netflow'))} data={netFlowData} />}
          <div className="mt-3 px-3 py-2 bg-surface2 rounded-lg text-xs text-muted2 border-l-2 border-warning">
            💡 A consistently positive net flow means the team is reducing WIP. Negative weeks signal backlog growth.
          </div>
        </div>
      </div>
    </div>
  )
}
