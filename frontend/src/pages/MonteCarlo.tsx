import { useState } from 'react'
import { useFilterStore } from '../store/filterStore'
import { useMonteCarlo } from '../api/hooks/useMetrics'
import MonteCarloChart from '../components/charts/MonteCarloChart'
import EmptyState from '../components/ui/EmptyState'
import type { MonteCarloResult } from '../types'
import clsx from 'clsx'

export default function MonteCarlo() {
  const { activeProjectId } = useFilterStore()
  const [mode, setMode] = useState<'when_done' | 'how_many'>('when_done')
  const [backlogSize, setBacklogSize] = useState(50)
  const [targetWeeks, setTargetWeeks] = useState(8)
  const [simulations] = useState(10000)
  const { mutate: runSim, data: result, isPending } = useMonteCarlo()

  if (!activeProjectId) return <EmptyState icon="◎" title="No project selected" description="Select a project from the sidebar." />

  const run = () => {
    runSim({
      project_id: activeProjectId,
      ...(mode === 'when_done' ? { backlog_size: backlogSize } : { target_weeks: targetWeeks }),
      simulations,
      weeks_history: 12,
    })
  }

  return (
    <div className="space-y-5 max-w-3xl">
      <div className="bg-surface border border-border rounded-xl p-5">
        <div className="text-sm font-bold mb-4">Forecast Parameters</div>

        {/* Mode toggle */}
        <div className="flex gap-2 mb-5">
          {(['when_done', 'how_many'] as const).map(m => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={clsx(
                'flex-1 py-2 rounded-lg text-sm font-medium transition-colors border',
                mode === m
                  ? 'bg-primary/15 border-primary text-primary'
                  : 'border-border text-muted2 hover:border-border2 hover:text-text'
              )}
            >
              {m === 'when_done' ? '📅 When will we finish?' : '📦 How many will we complete?'}
            </button>
          ))}
        </div>

        {mode === 'when_done' ? (
          <div>
            <label className="block text-xs font-semibold text-muted uppercase tracking-widest mb-2">Backlog size (items)</label>
            <input
              type="number" min={1} value={backlogSize}
              onChange={e => setBacklogSize(Number(e.target.value))}
              className="bg-surface2 border border-border text-text rounded-lg px-4 py-2 w-full focus:outline-none focus:border-primary text-sm"
            />
          </div>
        ) : (
          <div>
            <label className="block text-xs font-semibold text-muted uppercase tracking-widest mb-2">Target weeks</label>
            <input
              type="number" min={1} value={targetWeeks}
              onChange={e => setTargetWeeks(Number(e.target.value))}
              className="bg-surface2 border border-border text-text rounded-lg px-4 py-2 w-full focus:outline-none focus:border-primary text-sm"
            />
          </div>
        )}

        <button
          onClick={run}
          disabled={isPending}
          className="mt-4 w-full bg-primary hover:bg-primary/90 disabled:opacity-50 text-white rounded-lg py-2.5 text-sm font-semibold transition-colors"
        >
          {isPending ? 'Simulating 10,000 runs…' : '▶ Run Forecast'}
        </button>
      </div>

      {result && (
        <>
          {/* Percentile result cards */}
          <div className="grid grid-cols-4 gap-3">
            {[
              { key: '50', label: '50% confidence', color: '#22c55e' },
              { key: '70', label: '70% confidence', color: '#6366f1' },
              { key: '85', label: '85% confidence', color: '#f59e0b', highlight: true },
              { key: '95', label: '95% confidence', color: '#ef4444' },
            ].map(({ key, label, color, highlight }) => (
              <div key={key} className={clsx(
                'bg-surface border rounded-xl p-4 relative overflow-hidden',
                highlight ? 'border-warning/40' : 'border-border'
              )}>
                <div className="absolute top-0 left-0 right-0 h-[3px] rounded-t-xl" style={{ background: color }} />
                {highlight && <div className="text-[10px] font-bold text-warning uppercase tracking-widest mb-1">Recommended</div>}
                <div className="text-[11px] font-semibold text-muted uppercase tracking-widest mb-1">{label}</div>
                <div className="text-lg font-extrabold" style={{ color }}>
                  {result.percentiles[key] ?? '—'}
                </div>
              </div>
            ))}
          </div>

          {/* Chart */}
          <div className="bg-surface border border-border rounded-xl p-5">
            <div className="text-sm font-bold mb-1">Probability Distribution</div>
            <div className="text-xs text-muted mb-4">Monte Carlo simulation — {result.simulations.toLocaleString()} runs</div>
            <MonteCarloChart result={result} />
          </div>
        </>
      )}
    </div>
  )
}
