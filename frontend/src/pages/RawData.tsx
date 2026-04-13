import { useState } from 'react'
import { useFilterStore } from '../store/filterStore'
import { useRawData } from '../api/hooks/useMetrics'
import EmptyState from '../components/ui/EmptyState'
import { ChartSkeleton } from '../components/ui/LoadingSkeleton'
import client from '../api/client'

export default function RawData() {
  const { activeProjectId, weeks, itemType } = useFilterStore()
  const { data = [], isLoading } = useRawData(activeProjectId)
  const [search, setSearch] = useState('')

  if (!activeProjectId) return <EmptyState icon="⊞" title="No project selected" description="Select a project from the sidebar." />

  const filtered = (data as any[]).filter(row =>
    !search || JSON.stringify(row).toLowerCase().includes(search.toLowerCase())
  )

  const cols = data.length > 0 ? Object.keys((data as any[])[0]) : []

  const exportCsv = () => {
    window.open(`/api/metrics/${activeProjectId}/export-csv?weeks=${weeks}&item_type=${itemType}`)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <input
          type="text"
          placeholder="Search…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="bg-surface2 border border-border text-text text-sm rounded-lg px-4 py-2 w-64 focus:outline-none focus:border-primary"
        />
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
                {cols.map(col => (
                  <th key={col} className="text-left px-4 py-3 text-[10px] font-semibold text-muted uppercase tracking-widest whitespace-nowrap">
                    {col.replace(/_/g, ' ')}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.slice(0, 200).map((row: any, i) => (
                <tr key={i} className="border-b border-border/30 hover:bg-surface2 transition-colors">
                  {cols.map(col => (
                    <td key={col} className="px-4 py-2 text-muted2 whitespace-nowrap max-w-[180px] truncate">
                      {row[col] != null ? String(row[col]) : '—'}
                    </td>
                  ))}
                </tr>
              ))}
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
