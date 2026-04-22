import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useProjects, useDeleteProject } from '../api/hooks/useProjects'
import { useFilterStore } from '../store/filterStore'
import ProjectWizard from '../components/config/ProjectWizard'
import ProjectRow from './ProjectRow'
import type { Project } from '../types'

export default function Projects() {
  const navigate = useNavigate()
  const { data: projects = [], isLoading } = useProjects()
  const { mutate: deleteProject } = useDeleteProject()
  const { setActiveProject } = useFilterStore()
  const [showWizard, setShowWizard] = useState(false)
  const [editProject, setEditProject] = useState<Project | null>(null)

  const handleCreated = (id: number) => {
    setActiveProject(id)
    setShowWizard(false)
    setEditProject(null)
    navigate('/')
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

      {projects.map(project => (
        <ProjectRow
          key={project.id}
          project={project}
          onEdit={setEditProject}
          onDelete={deleteProject}
        />
      ))}

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
