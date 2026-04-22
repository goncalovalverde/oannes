import { useRef } from 'react'
import { useSyncStatus, useTriggerSync, useClearCache, useCsvUploadSync } from '../api/hooks/useSync'
import type { Project } from '../types'
import { formatDistanceToNow } from 'date-fns'
import clsx from 'clsx'

const PLATFORM_ICONS: Record<string, string> = {
  jira: '🔵', trello: '🟦', azure_devops: '🔷', gitlab: '🟠',
  linear: '🟣', shortcut: '🟢', csv: '📄',
}
const PLATFORM_LABELS: Record<string, string> = {
  jira: 'Jira', trello: 'Trello', azure_devops: 'Azure DevOps',
  gitlab: 'GitLab', linear: 'Linear', shortcut: 'Shortcut', csv: 'CSV / Excel',
}

interface ProjectRowProps {
  project: Project
  onEdit: (project: Project) => void
  onDelete: (id: number) => void
}

export default function ProjectRow({ project, onEdit, onDelete }: ProjectRowProps) {
  const { data: syncJob } = useSyncStatus(project.id)
  const { mutate: triggerSync } = useTriggerSync()
  const { mutate: clearCache } = useClearCache()
  const { mutate: csvUpload, isPending: isCsvUploading } = useCsvUploadSync()
  const csvFileRef = useRef<HTMLInputElement>(null)
  const isSyncActive = syncJob?.status === 'running' || syncJob?.status === 'pending' || isCsvUploading

  const handleSyncClick = () => {
    if (isSyncActive) {
      const progress = syncJob?.items_fetched ? ` (${syncJob.items_fetched} items)` : ''
      const status = syncJob?.status || 'syncing'
      alert(`Project is currently ${status}${progress}. Please wait until the sync completes.`)
      return
    }
    triggerSync(project.id)
  }

  const handleCsvFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    csvUpload({ projectId: project.id, file })
    // Reset so same file can be re-uploaded
    e.target.value = ''
  }

  const handleClearCache = () => {
    if (window.confirm(
      `Clear all cached data for "${project.name}"?\n\nThis will delete all cached items and force a fresh sync on the next sync operation. This action cannot be undone.`
    )) {
      clearCache(project.id)
    }
  }

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="text-2xl">{PLATFORM_ICONS[project.platform] ?? '📊'}</div>
          <div>
            <div className="font-semibold text-sm">{project.name}</div>
            <div className="text-xs text-muted mt-0.5">
              {PLATFORM_LABELS[project.platform]}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className={clsx(
            'text-[10px] font-semibold px-2 py-0.5 rounded-full',
            isSyncActive ? 'bg-warning/15 text-warning animate-pulse' : (project.last_synced_at ? 'bg-success/15 text-success' : 'bg-warning/15 text-warning')
          )}>
            {isSyncActive
              ? `Syncing${syncJob?.items_fetched ? ` (${syncJob.items_fetched} items)` : '…'}`
              : (project.last_synced_at
              ? `Synced ${formatDistanceToNow(new Date(project.last_synced_at), { addSuffix: true })}`
              : 'Never synced')}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2 mt-4 pt-4 border-t border-border">
        {project.platform === 'csv' ? (
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
              className="text-xs text-muted2 border border-border rounded-md px-3 py-1.5 hover:border-primary hover:text-primary transition-colors disabled:opacity-50"
            >
              {isCsvUploading ? '⏳ Importing…' : '↑ Upload File'}
            </button>
          </>
        ) : (
          <button
            onClick={handleSyncClick}
            className="text-xs text-muted2 border border-border rounded-md px-3 py-1.5 hover:border-primary hover:text-primary transition-colors"
          >
            ↻ Sync Now
          </button>
        )}
        <button
          onClick={() => onEdit(project)}
          className="text-xs text-muted2 border border-border rounded-md px-3 py-1.5 hover:border-primary hover:text-primary transition-colors"
        >
          ✏ Edit
        </button>
        <button
          onClick={handleClearCache}
          className="text-xs text-muted2 border border-border rounded-md px-3 py-1.5 hover:border-warning hover:text-warning transition-colors"
          title="Clear all cached data and force a fresh sync"
        >
          🔄 Reset Cache
        </button>
        <button
          onClick={() => {
            if (window.confirm(`Delete project "${project.name}"? This will remove all cached data.`)) {
              onDelete(project.id)
            }
          }}
          className="text-xs text-muted2 border border-border rounded-md px-3 py-1.5 hover:border-danger hover:text-danger transition-colors ml-auto"
        >
          🗑 Delete
        </button>
      </div>
    </div>
  )
}
