import { useRef } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import clsx from 'clsx'
import { useProjects } from '../../api/hooks/useProjects'
import { useFilterStore } from '../../store/filterStore'
import { useSyncStatus, useTriggerSync, useCsvUploadSync } from '../../api/hooks/useSync'
import { formatDistanceToNow } from 'date-fns'

const NAV = [
  { to: '/',            icon: '◈', label: 'Dashboard' },
  { section: 'Metrics' },
  { to: '/throughput',  icon: '↑', label: 'Throughput' },
  { to: '/cycle-time',  icon: '⏱', label: 'Cycle Time' },
  { to: '/lead-time',   icon: '⤳', label: 'Lead Time' },
  { to: '/wip',         icon: '≋', label: 'WIP' },
  { to: '/cfd',         icon: '∿', label: 'Flow / CFD' },
  { to: '/aging-wip',   icon: '⧗', label: 'Aging WIP' },
  { section: 'Forecast' },
  { to: '/monte-carlo', icon: '◎', label: 'Monte Carlo' },
  { section: 'Data' },
  { to: '/raw-data',    icon: '⊞', label: 'Raw Data' },
  { section: 'Settings' },
  { to: '/projects',    icon: '⚙', label: 'Projects' },
]

export default function Sidebar() {
  const { data: projects = [] } = useProjects()
  const { activeProjectId, setActiveProject } = useFilterStore()
  const activeProject = projects.find(p => p.id === activeProjectId) ?? projects[0]
  const navigate = useNavigate()

  const { data: syncJob } = useSyncStatus(activeProject?.id ?? null)
  const { mutate: triggerSync, isPending: isSyncing } = useTriggerSync()
  const { mutate: csvUpload, isPending: isCsvUploading } = useCsvUploadSync()
  const csvFileRef = useRef<HTMLInputElement>(null)

  const lastSynced = activeProject?.last_synced_at
    ? formatDistanceToNow(new Date(activeProject.last_synced_at), { addSuffix: true })
    : 'Never'

  const isSyncActive = syncJob?.status === 'running' || syncJob?.status === 'pending' || isSyncing || isCsvUploading

  const handleSyncClick = () => {
    if (!activeProject) return

    if (isSyncActive) {
      const progress = syncJob?.items_fetched ? ` (${syncJob.items_fetched} items)` : ''
      const status = syncJob?.status || 'syncing'
      alert(`Project is currently ${status}${progress}. Please wait until the sync completes.`)
      return
    }

    triggerSync(activeProject.id)
  }

  const handleCsvFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !activeProject) return
    csvUpload({ projectId: activeProject.id, file })
    e.target.value = ''
  }

  return (
    <aside className="w-[220px] min-w-[220px] bg-surface border-r border-border flex flex-col h-full">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-border flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center text-white font-extrabold text-base"
          style={{ background: 'linear-gradient(135deg, #6366f1, #a78bfa)' }}>
          O
        </div>
        <div>
          <div className="text-[15px] font-bold tracking-tight">Oannes</div>
          <div className="text-[10px] text-muted">Flow Metrics v2</div>
        </div>
      </div>

      {/* Project selector */}
      {projects.length > 0 && (
        <div className="mx-3 mt-3">
          <select
            value={activeProject?.id ?? ''}
            onChange={e => setActiveProject(Number(e.target.value))}
            className="w-full bg-surface2 border border-border text-text text-xs rounded-md px-3 py-2 focus:outline-none focus:border-primary cursor-pointer"
          >
            {projects.map(p => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>
      )}

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-2 px-2">
        {NAV.map((item, i) => {
          if ('section' in item) {
            return (
              <div key={i} className="text-[10px] font-semibold text-muted uppercase tracking-widest px-2 pt-4 pb-1">
                {item.section}
              </div>
            )
          }
          return (
            <NavLink
              key={item.to}
              to={item.to!}
              end={item.to === '/'}
              className={({ isActive }) => clsx(
                'flex items-center gap-2.5 px-2.5 py-[7px] rounded-md text-[13px] font-medium transition-colors',
                isActive
                  ? 'bg-primary/15 text-primary'
                  : 'text-muted2 hover:bg-surface2 hover:text-text'
              )}
            >
              <span className="w-4 text-center text-sm">{item.icon}</span>
              {item.label}
            </NavLink>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="p-3 border-t border-border space-y-2">
        <div className="flex items-center gap-2 text-[11px] text-muted bg-surface2 rounded-md px-3 py-2">
          <span className={clsx(
            'w-2 h-2 rounded-full flex-shrink-0',
            isSyncActive ? 'bg-warning animate-pulse' : 'bg-success'
          )} style={{ boxShadow: isSyncActive ? '0 0 6px #f59e0b' : '0 0 6px #22c55e' }} />
          <span>{isSyncActive ? 'Syncing…' : `Synced ${lastSynced}`}</span>
        </div>
        {activeProject?.platform === 'csv' ? (
          <>
            <input
              ref={csvFileRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              className="hidden"
              onChange={handleCsvFileChange}
            />
            <button
              onClick={() => csvFileRef.current?.click()}
              disabled={isSyncActive}
              className="w-full text-xs font-medium text-muted2 border border-border rounded-md py-1.5 hover:border-primary hover:text-primary transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {isCsvUploading ? '⏳ Importing…' : '↑ Upload File'}
            </button>
          </>
        ) : (
          <button
            onClick={handleSyncClick}
            className="w-full text-xs font-medium text-muted2 border border-border rounded-md py-1.5 hover:border-primary hover:text-primary transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            ↻ Sync Now
          </button>
        )}
      </div>
    </aside>
  )
}
