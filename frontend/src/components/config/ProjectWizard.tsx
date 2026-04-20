import { useState, useEffect } from 'react'
import { useCreateProject, useUpdateProject, useTestConnection, useDiscoverStatuses } from '../../api/hooks/useProjects'
import type { Project, ProjectInput } from '../../types'
import AlertBanner from '../ui/AlertBanner'
import clsx from 'clsx'

const PLATFORMS = [
  { id: 'jira',        label: 'Jira',         icon: '🔵', desc: 'Jira Cloud or Server' },
  { id: 'trello',      label: 'Trello',        icon: '🟦', desc: 'Boards & cards' },
  { id: 'azure_devops',label: 'Azure DevOps',  icon: '🔷', desc: 'Work items & boards' },
  { id: 'gitlab',      label: 'GitLab',        icon: '🟠', desc: 'Issues & milestones' },
  { id: 'linear',      label: 'Linear',        icon: '🟣', desc: 'Coming soon', disabled: true },
  { id: 'shortcut',    label: 'Shortcut',      icon: '🟢', desc: 'Coming soon', disabled: true },
  { id: 'csv',         label: 'CSV / Excel',   icon: '📄', desc: 'Import from file' },
]

const PLATFORM_FIELDS: Record<string, Array<{ key: string; label: string; type?: string; placeholder?: string; help?: string; optional?: boolean; default?: string; options?: Array<{value: string; label: string}>; conditional?: (config: Record<string, string>) => boolean }>> = {
  jira: [
    { key: 'url',       label: 'Jira URL',    placeholder: 'https://yourcompany.atlassian.net' },
    { key: 'auth_type', label: 'Authentication Type', type: 'select', optional: false, default: 'api_token', options: [{ value: 'api_token', label: 'API Token (Email + Token)' }, { value: 'personal_access_token', label: 'Personal Access Token' }], help: 'Choose based on your Jira instance configuration' },
    { key: 'email',     label: 'Email',       type: 'email', placeholder: 'you@company.com', conditional: (cfg) => cfg.auth_type === 'api_token' },
    { key: 'api_token', label: 'API Token',   type: 'password', help: 'Create at: id.atlassian.com/manage-profile/security/api-tokens', conditional: (cfg) => cfg.auth_type === 'api_token' },
    { key: 'personal_access_token', label: 'Personal Access Token', type: 'password', help: 'Create at: your Jira instance → Profile → Personal Access Tokens', conditional: (cfg) => cfg.auth_type === 'personal_access_token' },
    { key: 'jira_api_version', label: 'Jira API Version', type: 'select', optional: false, default: 'auto', options: [{ value: 'auto', label: 'Auto-detect (recommended)' }, { value: 'v3', label: 'Force v3 (Cloud)' }, { value: 'v2', label: 'Force v2 (Server/Data Center)' }], help: '⚠️ Most users should use "Auto-detect". Only change if you know your Jira version.' },
    { key: 'jql',       label: 'JQL Filter',  placeholder: 'project = MYPROJ', optional: true },
  ],
  trello: [
    { key: 'api_key', label: 'API Key',  help: 'Get at: trello.com/app-key' },
    { key: 'token',   label: 'Token',   type: 'password', help: 'Authorize at: trello.com/app-key then click Token' },
  ],
  azure_devops: [
    { key: 'org_url',              label: 'Organization URL',     placeholder: 'https://dev.azure.com/yourorg' },
    { key: 'personal_access_token', label: 'Personal Access Token', type: 'password', help: 'Create at: dev.azure.com → User settings → Personal access tokens' },
  ],
  gitlab: [
    { key: 'url',          label: 'GitLab URL',    placeholder: 'https://gitlab.com' },
    { key: 'access_token', label: 'Access Token',  type: 'password', help: 'Create at: GitLab → Profile → Access Tokens (api scope)' },
  ],
  csv: [
    { key: 'file_path', label: 'File Path', placeholder: '/path/to/data.csv', help: 'Required columns: item_key, item_type, created_at + workflow step date columns' },
  ],
}

const STAGES = ['queue', 'start', 'in_flight', 'done'] as const
const STAGE_LABELS: Record<string, string> = { queue: 'Queue', start: 'Start', in_flight: 'In Flight', done: 'Done' }
const STAGE_DESCS: Record<string, string> = {
  queue:     'Not yet started',
  start:     'Cycle time begins here',
  in_flight: 'Active work stages',
  done:      'Cycle time ends here',
}

interface Props {
  existing?: Project
  onClose: () => void
  onSaved: (id: number) => void
}

export default function ProjectWizard({ existing, onClose, onSaved }: Props) {
  const [step, setStep] = useState(existing ? 2 : 1)
  const [platform, setPlatform] = useState(existing?.platform ?? '')
  const [name, setName] = useState(existing?.name ?? '')
  const [config, setConfig] = useState<Record<string, string>>(() => {
    const baseConfig = existing?.config ?? {}
    // Set defaults for Jira if creating new project
    if (!existing) {
      if (!baseConfig.auth_type) {
        baseConfig.auth_type = 'api_token'
      }
      if (!baseConfig.jira_api_version) {
        baseConfig.jira_api_version = 'auto'
      }
    }
    return baseConfig
  })
  const [boards, setBoards] = useState<Array<{ id: string; name: string }>>([])
  const [selectedBoard, setSelectedBoard] = useState(existing?.config?.project_key ?? '')
  const [statuses, setStatuses] = useState<string[]>([])
  const [workflowMap, setWorkflowMap] = useState<Record<string, string>>(
    Object.fromEntries(existing?.workflow_steps?.map(s => s.source_statuses.map(ss => [ss, s.stage])).flat() ?? [])
  )
  const [testResult, setTestResult] = useState<{ success: boolean; message: string; api_version_detected?: string | null } | null>(null)
  const [validationErrors, setValidationErrors] = useState<string[]>([])
  const [draggedStatus, setDraggedStatus] = useState<string | null>(null)
  const [dragOverStage, setDragOverStage] = useState<string | null>(null)

  // Set default auth_type and api_version for Jira when platform is selected
  useEffect(() => {
    if (platform === 'jira') {
      if (!config.auth_type) {
        setConfig(c => ({ ...c, auth_type: 'api_token' }))
      }
      if (!config.jira_api_version) {
        setConfig(c => ({ ...c, jira_api_version: 'auto' }))
      }
    }
  }, [platform])

  // Validate required fields
  const getValidationErrors = (): string[] => {
    const errors: string[] = []
    
    // Project name is always required
    if (!name.trim()) {
      errors.push('Project name is required')
    }

    const fields = PLATFORM_FIELDS[platform] ?? []
    for (const field of fields) {
      if (field.optional) continue
      
      // Check if field should be shown (respects conditional rendering)
      const shouldShow = !field.conditional || field.conditional(config)
      if (!shouldShow) continue

      // Check if field is filled
      const value = config[field.key]?.trim()
      if (!value) {
        errors.push(`${field.label} is required`)
      }
    }

    return errors
  }

  const { mutate: testConn, isPending: isTesting } = useTestConnection()
  const { mutate: discoverStatuses } = useDiscoverStatuses()
  const { mutate: createProject, isPending: isCreating } = useCreateProject()
  const { mutate: updateProject, isPending: isUpdating } = useUpdateProject()

  const handleTest = () => {
    const errors = getValidationErrors()
    if (errors.length > 0) {
      setValidationErrors(errors)
      return
    }
    setValidationErrors([])
    testConn({ platform, config }, {
      onSuccess: (res) => {
        setTestResult({ success: res.success, message: res.message })
        if (res.success) setBoards(res.projects_found ?? [])
      },
      onError: (e) => setTestResult({ success: false, message: String(e) }),
    })
  }

  const handleDiscover = () => {
    if (!selectedBoard) return
    discoverStatuses(
      { platform, config: { ...config, project_key: selectedBoard }, board_id: selectedBoard },
      { onSuccess: (res) => setStatuses(res.statuses ?? []) }
    )
  }

  const handleSave = () => {
    const steps = STAGES.flatMap((stage, i) => {
      const sources = Object.entries(workflowMap).filter(([, s]) => s === stage).map(([ss]) => ss)
      if (sources.length === 0) return []
      return [{ position: i, display_name: STAGE_LABELS[stage], source_statuses: sources, stage }]
    })

    const projectData: ProjectInput = {
      name,
      platform: platform as Project['platform'],
      config: { ...config, project_key: selectedBoard },
      workflow_steps: steps,
    }

    if (existing) {
      updateProject({ id: existing.id, data: projectData }, { onSuccess: () => onSaved(existing.id) })
    } else {
      createProject(projectData, { onSuccess: (p) => onSaved(p.id) })
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-surface border border-border rounded-2xl w-full max-w-xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-border">
          <div>
            <div className="font-bold text-sm">{existing ? 'Edit Project' : 'New Project'}</div>
            <div className="text-xs text-muted mt-0.5">Step {step} of 3</div>
          </div>
          <button onClick={onClose} className="text-muted hover:text-text text-xl leading-none">×</button>
        </div>

        {/* Progress */}
        <div className="flex gap-1 px-5 pt-4">
          {[1, 2, 3].map(s => (
            <div key={s} className={clsx('h-1 flex-1 rounded-full transition-colors', s <= step ? 'bg-primary' : 'bg-border')} />
          ))}
        </div>

        <div className="p-5 space-y-4">
          {/* Step 1: Platform */}
          {step === 1 && (
            <>
              <div className="text-sm font-semibold">Choose your platform</div>
              <div className="grid grid-cols-3 gap-3">
                {PLATFORMS.map(p => (
                  <button
                    key={p.id}
                    disabled={p.disabled}
                    onClick={() => { setPlatform(p.id); setConfig({}) }}
                    className={clsx(
                      'p-3 rounded-xl border text-left transition-all',
                      p.disabled ? 'opacity-40 cursor-not-allowed border-border' :
                        platform === p.id ? 'border-primary bg-primary/10' : 'border-border hover:border-border2'
                    )}
                  >
                    <div className="text-xl mb-1">{p.icon}</div>
                    <div className="text-xs font-semibold">{p.label}</div>
                    <div className="text-[10px] text-muted mt-0.5">{p.desc}</div>
                  </button>
                ))}
              </div>
              <div className="flex justify-end pt-2">
                <button
                  disabled={!platform}
                  onClick={() => setStep(2)}
                  className="bg-primary disabled:opacity-40 text-white text-sm font-semibold rounded-lg px-5 py-2 transition-colors"
                >
                  Next →
                </button>
              </div>
            </>
          )}

          {/* Step 2: Credentials */}
          {step === 2 && (
            <>
              <div className="text-sm font-semibold">Connect to {PLATFORMS.find(p => p.id === platform)?.label}</div>

              <div>
                <label className="block text-[11px] font-semibold text-muted uppercase tracking-widest mb-1">Project Name</label>
                <input
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="My Team"
                  className="w-full bg-surface2 border border-border text-text text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-primary"
                />
              </div>

              {(PLATFORM_FIELDS[platform] ?? []).map(field => {
                const shouldShow = !field.conditional || field.conditional(config)
                if (!shouldShow) return null
                
                return (
                  <div key={field.key}>
                    <label className="block text-[11px] font-semibold text-muted uppercase tracking-widest mb-1">
                      {field.label} {field.optional && <span className="normal-case text-muted font-normal">(optional)</span>}
                    </label>
                    {field.type === 'select' ? (
                      <select
                        value={config[field.key] ?? field.default ?? ''}
                        onChange={e => setConfig(c => ({ ...c, [field.key]: e.target.value }))}
                        className="w-full bg-surface2 border border-border text-text text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-primary"
                      >
                        <option value="">-- Select --</option>
                        {field.options?.map(opt => (
                          <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                      </select>
                    ) : (
                      <input
                        type={field.type ?? 'text'}
                        placeholder={field.placeholder}
                        value={config[field.key] ?? ''}
                        onChange={e => setConfig(c => ({ ...c, [field.key]: e.target.value }))}
                        className="w-full bg-surface2 border border-border text-text text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-primary"
                      />
                    )}
                    {field.help && <div className="text-[10px] text-muted mt-1">💡 {field.help}</div>}
                  </div>
                )
              })}

              {validationErrors.length > 0 && (
                <AlertBanner type="error">
                  <div className="space-y-1">
                    {validationErrors.map((err, i) => (
                      <div key={i}>⚠️ {err}</div>
                    ))}
                  </div>
                </AlertBanner>
              )}

              <button
                onClick={handleTest}
                disabled={isTesting}
                className="w-full border border-border text-sm font-medium text-muted2 hover:border-primary hover:text-primary rounded-lg py-2 transition-colors disabled:opacity-50"
              >
                {isTesting ? 'Testing connection…' : '🔌 Test Connection'}
              </button>

              {isTesting && (
                <AlertBanner type="info">
                  <div className="flex items-center gap-3">
                    <div className="flex gap-1">
                      <div className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <div className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <div className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                    <span>Checking connection status…</span>
                  </div>
                </AlertBanner>
              )}

              {testResult && (
                <AlertBanner type={testResult.success ? 'info' : 'error'}>
                  <div>
                    <div>{testResult.message}</div>
                    {testResult.api_version_detected && (
                      <div className="text-[10px] mt-1 opacity-75">
                        API Version: {testResult.api_version_detected.toUpperCase()}
                      </div>
                    )}
                  </div>
                </AlertBanner>
              )}

              {boards.length > 0 && (
                <div>
                  <label className="block text-[11px] font-semibold text-muted uppercase tracking-widest mb-1">Select Project / Board</label>
                  <select
                    value={selectedBoard}
                    onChange={e => setSelectedBoard(e.target.value)}
                    className="w-full bg-surface2 border border-border text-text text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-primary"
                  >
                    <option value="">Choose…</option>
                    {boards.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
                  </select>
                </div>
              )}

              <div className="flex justify-between pt-2">
                <button onClick={() => setStep(1)} className="text-sm text-muted2 hover:text-text px-3 py-2">← Back</button>
                <button
                  disabled={!name || !testResult?.success}
                  onClick={() => { setStep(3); handleDiscover() }}
                  className="bg-primary disabled:opacity-40 text-white text-sm font-semibold rounded-lg px-5 py-2"
                >
                  Next →
                </button>
              </div>
            </>
          )}

          {/* Step 3: Workflow Mapping */}
          {step === 3 && (
            <>
              <div className="text-sm font-semibold">Map your workflow</div>
              <div className="text-xs text-muted2">Assign each status to a stage. Cycle time is measured from <strong className="text-text">Start → Done</strong>.</div>

              {statuses.length === 0 && (
                <div className="text-xs text-muted italic">No statuses discovered — you can add them manually or skip this step.</div>
              )}

              <div className="grid grid-cols-2 gap-3">
                {STAGES.map(stage => (
                  <div
                    key={stage}
                    onDragOver={(e) => {
                      e.preventDefault()
                      e.currentTarget.classList.add('ring-2', 'ring-primary/50')
                      setDragOverStage(stage)
                    }}
                    onDragLeave={(e) => {
                      e.currentTarget.classList.remove('ring-2', 'ring-primary/50')
                      setDragOverStage(null)
                    }}
                    onDrop={(e) => {
                      e.preventDefault()
                      e.currentTarget.classList.remove('ring-2', 'ring-primary/50')
                      const status = e.dataTransfer?.getData('text/plain')
                      if (status) {
                        setWorkflowMap(m => ({ ...m, [status]: stage }))
                      }
                      setDragOverStage(null)
                    }}
                    className={clsx(
                      'bg-surface2 border border-border rounded-xl p-3 transition-all duration-150',
                      dragOverStage === stage && 'ring-2 ring-primary/50 bg-primary/5'
                    )}
                  >
                    <div className="text-xs font-semibold text-muted uppercase tracking-widest mb-0.5">{STAGE_LABELS[stage]}</div>
                    <div className="text-[10px] text-muted mb-2">{STAGE_DESCS[stage]}</div>
                    <div className="flex flex-wrap gap-1 min-h-[40px]">
                      {statuses.filter(s => workflowMap[s] === stage).map(s => (
                        <span
                          key={s}
                          draggable
                          onDragStart={(e) => {
                            e.dataTransfer?.setData('text/plain', s)
                            setDraggedStatus(s)
                          }}
                          onDragEnd={() => setDraggedStatus(null)}
                          className={clsx(
                            'bg-primary/20 text-primary text-[10px] font-medium px-2 py-0.5 rounded cursor-grab active:cursor-grabbing hover:bg-danger/20 hover:text-danger transition-all duration-150 flex items-center gap-1 select-none',
                            draggedStatus === s && 'opacity-50'
                          )}
                        >
                          {s}
                          <button
                            onClick={() => setWorkflowMap(m => { const n = { ...m }; delete n[s]; return n })}
                            className="ml-0.5 hover:opacity-70"
                            title="Remove assignment"
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              {/* Unassigned statuses */}
              <div>
                <div className="text-[11px] font-semibold text-muted uppercase tracking-widest mb-2">Unassigned statuses — drag to assign</div>
                <div
                  onDragOver={(e) => {
                    e.preventDefault()
                    e.currentTarget.classList.add('ring-1', 'ring-muted/30')
                  }}
                  onDragLeave={(e) => {
                    e.currentTarget.classList.remove('ring-1', 'ring-muted/30')
                  }}
                  onDrop={(e) => {
                    e.preventDefault()
                    e.currentTarget.classList.remove('ring-1', 'ring-muted/30')
                    const status = e.dataTransfer?.getData('text/plain')
                    if (status && workflowMap[status]) {
                      setWorkflowMap(m => { const n = { ...m }; delete n[status]; return n })
                    }
                  }}
                  className={clsx(
                    'flex flex-wrap gap-2 p-3 bg-surface border border-border rounded-lg transition-all duration-150 min-h-[50px]',
                    dragOverStage === null && draggedStatus && 'ring-1 ring-muted/30'
                  )}
                >
                  {statuses.filter(s => !workflowMap[s]).map(s => (
                    <span
                      key={s}
                      draggable
                      onDragStart={(e) => {
                        e.dataTransfer?.setData('text/plain', s)
                        setDraggedStatus(s)
                      }}
                      onDragEnd={() => setDraggedStatus(null)}
                      className={clsx(
                        'bg-surface2 border border-border text-muted2 text-xs px-2 py-1 rounded cursor-grab active:cursor-grabbing hover:bg-primary/10 hover:text-text transition-all duration-150 select-none',
                        draggedStatus === s && 'opacity-50'
                      )}
                    >
                      {s}
                    </span>
                  ))}
                </div>
              </div>

              <div className="flex justify-between pt-2">
                <button onClick={() => setStep(2)} className="text-sm text-muted2 hover:text-text px-3 py-2">← Back</button>
                <button
                  disabled={isCreating || isUpdating}
                  onClick={handleSave}
                  className="bg-primary disabled:opacity-40 text-white text-sm font-semibold rounded-lg px-5 py-2"
                >
                  {isCreating || isUpdating ? 'Saving…' : '✓ Save & Start Sync'}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
