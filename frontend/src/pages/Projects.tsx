import { useState } from 'react'
import { useProjects, useDeleteProject } from '../api/hooks/useProjects'
import { useTriggerSync, useSyncStatus } from '../api/hooks/useSync'
import { useFilterStore } from '../store/filterStore'
import ProjectWizard from '../components/config/ProjectWizard'
import type { Project } from '../types'
import { formatDistanceToNow } from 'date-fns'
import clsx from 'clsx'

const PLATFORM_ICONS: Record<string, string> = {
  jira: '🔵', trello: '🟦', azure_devops: '🔷', gitlab: '🟠',
  linear: '🟣', shortcut: '🟢', csv: '📄',
}
const PLATFORM_LABELS: Record<string, string> = {
  jira: 'Jira', trello: 'Trello', azure_devops: 'Azure DevOps',
  gitlab: 'GitLab', linear: 'Linear', shortcut: 'Shortcut', csv: 'CSV',
}

export default function Projects() {
  const { data: projects = [], isLoading } = useProjects()
  const { mutate: deleteProject } = useDeleteProject()
  const { mutate: triggerSync } = useTriggerSync()
  const { setActiveProject } = useFilterStore()
  const [showWizard, setShowWizard] = useState(false)
  const [editProject, setEditProject] = useState<Project | null>(null)

  const handleCreated = (id: number) => {
    setActiveProject(id)
    setShowWizard(false)
    setEditProject(null)
  }

  return (
    <div className="max-w-3xl space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold">Connected Projects</h2>
          <p className="text-xs text-muted mt-0.5">Manage your data sources and workflow mappings</p>
        </div>
        <button
          onClick={() => setShowWizard(true)}
          className="bg-primary hover:bg-primary/90 text-white text-sm font-semibold rounded-lg px-4 py-2 transition-colors"
        >
          + New Project
        </button>
      </div>

      {isLoading && (
        <div className="text-sm text-muted">Loading…</div>
      )}

      {!isLoading && projects.length === 0 && (
        <div className="bg-surface border border-border rounded-xl p-10 text-center">
          <div className="text-4xl mb-3">🌀</div>
          <div className="text-sm font-semibold text-text mb-1">No projects yet</div>
          <div className="text-xs text-muted mb-4">Connect Jira, Trello, Azure DevOps, GitLab or upload a CSV to get started.</div>
          <button onClick={() => setShowWizard(true)} className="bg-primary text-white text-sm font-semibold rounded-lg px-4 py-2">
            + Connect a project
          </button>
        </div>
      )}

      {projects.map(project => {
        // eslint-disable-next-line react-hooks/rules-of-hooks
        const { data: syncJob } = useSyncStatus(project.id)
        const isSyncActive = syncJob?.status === 'running' || syncJob?.status === 'pending'

        const handleSyncClick = () => {
          if (isSyncActive) {
            const progress = syncJob?.items_fetched ? ` (${syncJob.items_fetched} items)` : ''
            const status = syncJob?.status || 'syncing'
            alert(`Project is currently ${status}${progress}. Please wait until the sync completes.`)
            return
          }
          triggerSync(project.id)
        }

        return (
        <div key={project.id} className="bg-surface border border-border rounded-xl p-5">
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
            <button
              onClick={handleSyncClick}
              className="text-xs text-muted2 border border-border rounded-md px-3 py-1.5 hover:border-primary hover:text-primary transition-colors"
            >
              ↻ Sync Now
            </button>
            <button
              onClick={() => setEditProject(project)}
              className="text-xs text-muted2 border border-border rounded-md px-3 py-1.5 hover:border-primary hover:text-primary transition-colors"
            >
              ✏ Edit
            </button>
            <button
              onClick={() => {
                if (window.confirm(`Delete project "${project.name}"? This will remove all cached data.`)) {
                  deleteProject(project.id)
                }
              }}
              className="text-xs text-muted2 border border-border rounded-md px-3 py-1.5 hover:border-danger hover:text-danger transition-colors ml-auto"
            >
              🗑 Delete
            </button>
          </div>
        </div>
        )
      })}

      {(showWizard || editProject) && (
        <ProjectWizard
          existing={editProject ?? undefined}
          onClose={() => { setShowWizard(false); setEditProject(null) }}
          onSaved={handleCreated}
        />
      )}
    </div>
  )
}
