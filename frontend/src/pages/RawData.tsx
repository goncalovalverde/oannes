import { useState } from 'react'
import { useFilterStore } from '../store/filterStore'
import { useRawData } from '../api/hooks/useMetrics'
import EmptyState from '../components/ui/EmptyState'
import { ChartSkeleton } from '../components/ui/LoadingSkeleton'

interface Transition {
  from_status: string | null
  to_status: string
  transitioned_at: string
}

export default function RawData() {
  const { activeProjectId, weeks, itemType, setWeeks } = useFilterStore()
  const { data = [], isLoading } = useRawData(activeProjectId, weeks, itemType)
  const [search, setSearch] = useState('')
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  if (!activeProjectId) return <EmptyState icon="⊞" title="No project selected" description="Select a project from the sidebar." />

  const filtered = (data as any[]).filter(row =>
    !search || JSON.stringify(row).toLowerCase().includes(search.toLowerCase())
  )

  // columns = the flat data columns from the API (excludes status_transitions)
  const displayCols: string[] = data.length > 0
    ? Object.keys((data as any[])[0]).filter(k => k !== 'status_transitions')
    : []

  const exportCsv = () => {
    window.open(`/api/metrics/${activeProjectId}/export-csv?weeks=${weeks}&item_type=${itemType}`)
  }

  const toggleRow = (i: number) => {
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(i) ? next.delete(i) : next.add(i)
      return next
    })
  }

  const formatTs = (ts: string) => ts ? ts.replace('T', ' ').slice(0, 16) : '—'

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <input
          type="text"
          placeholder="Search…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="bg-surface2 border border-border text-text text-sm rounded-lg px-4 py-2 w-64 focus:outline-none focus:border-primary"
        />
        
        <select
          value={weeks}
          onChange={e => setWeeks(Number(e.target.value))}
          className="bg-surface2 border border-border text-text text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-primary"
        >
          <option value={4}>Last 4 weeks</option>
          <option value={12}>Last 12 weeks</option>
          <option value={26}>Last 26 weeks</option>
          <option value={52}>Last 52 weeks</option>
          <option value={104}>Last 2 years</option>
          <option value={260}>Last 5 years</option>
          <option value={520}>All data</option>
        </select>
        
        <button
          onClick={exportCsv}
          className="bg-surface2 border border-border text-muted2 hover:text-text hover:border-primary text-sm font-medium rounded-lg px-4 py-2 transition-colors"
        >
          ↓ Export CSV
        </button>
      </div>

      <div className="bg-surface border border-border rounded-xl overflow-x-auto">
        {isLoading ? (
          <div className="p-6"><ChartSkeleton /></div>
        ) : filtered.length === 0 ? (
          <div className="p-8 text-center text-muted text-sm">No data. Run a sync first.</div>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                {/* expand toggle column */}
                <th className="px-2 py-3 w-8" />
                {displayCols.map((col: string) => (
                  <th key={col} className="text-left px-4 py-3 text-[10px] font-semibold text-muted uppercase tracking-widest whitespace-nowrap">
                    {col.replace(/_/g, ' ')}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.slice(0, 200).map((row: any, i: number) => {
                const transitions: Transition[] = row.status_transitions ?? []
                const isOpen = expanded.has(i)
                return (
                  <>
                    <tr
                      key={`row-${i}`}
                      className={`border-b border-border/30 hover:bg-surface2 transition-colors ${transitions.length > 0 ? 'cursor-pointer' : ''}`}
                      onClick={() => transitions.length > 0 && toggleRow(i)}
                    >
                      <td className="px-2 py-2 text-center text-muted select-none">
                        {transitions.length > 0 ? (
                          <span className="text-primary font-bold">{isOpen ? '▼' : '▶'}</span>
                        ) : null}
                      </td>
                      {displayCols.map((col: string) => (
                        <td key={col} className="px-4 py-2 text-muted2 whitespace-nowrap max-w-[180px] truncate">
                          {row[col] != null ? String(row[col]) : '—'}
                        </td>
                      ))}
                    </tr>
                    {isOpen && transitions.length > 0 && (
                      <tr key={`expand-${i}`} className="bg-surface2/60 border-b border-border/30">
                        <td />
                        <td colSpan={displayCols.length} className="px-6 py-3">
                          <div className="text-[10px] font-semibold text-muted uppercase tracking-widest mb-2">
                            Status Transitions ({transitions.length})
                          </div>
                          <table className="w-full text-xs border border-border/40 rounded-lg overflow-hidden">
                            <thead>
                              <tr className="bg-surface border-b border-border/40">
                                <th className="text-left px-3 py-2 text-[10px] font-semibold text-muted uppercase tracking-widest">#</th>
                                <th className="text-left px-3 py-2 text-[10px] font-semibold text-muted uppercase tracking-widest">From</th>
                                <th className="text-left px-3 py-2 text-[10px] font-semibold text-muted uppercase tracking-widest">To</th>
                                <th className="text-left px-3 py-2 text-[10px] font-semibold text-muted uppercase tracking-widest">Date</th>
                              </tr>
                            </thead>
                            <tbody>
                              {transitions.map((t, j) => (
                                <tr key={j} className="border-b border-border/20 last:border-0 hover:bg-surface/80">
                                  <td className="px-3 py-1.5 text-muted">{j + 1}</td>
                                  <td className="px-3 py-1.5 text-muted2">{t.from_status ?? <span className="italic text-muted">—</span>}</td>
                                  <td className="px-3 py-1.5 text-text font-medium">{t.to_status}</td>
                                  <td className="px-3 py-1.5 text-muted2 whitespace-nowrap">{formatTs(t.transitioned_at)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </td>
                      </tr>
                    )}
                  </>
                )
              })}
            </tbody>
          </table>
        )}
        {filtered.length > 200 && (
          <div className="px-4 py-2 text-xs text-muted border-t border-border">
            Showing 200 of {filtered.length} rows
          </div>
        )}
      </div>
    </div>
  )
}
