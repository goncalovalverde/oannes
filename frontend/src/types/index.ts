export interface WorkflowStep {
  id: number
  project_id: number
  position: number
  display_name: string
  source_statuses: string[]
  stage: 'queue' | 'start' | 'in_flight' | 'done'
}

export interface Project {
  id: number
  name: string
  platform: 'jira' | 'trello' | 'azure_devops' | 'gitlab' | 'linear' | 'shortcut' | 'csv'
  config: Record<string, any>
  sync_frequency: 'hourly' | 'manual'
  last_synced_at: string | null
  created_at: string
  workflow_steps: WorkflowStep[]
}

export interface SyncJob {
  id: number
  project_id: number
  status: 'pending' | 'running' | 'success' | 'error'
  started_at: string | null
  finished_at: string | null
  error_message: string | null
  items_fetched: number | null
}

export interface MetricsSummary {
  throughput_avg: number
  throughput_trend_pct: number
  cycle_time_50th: number | null
  cycle_time_85th: number | null
  cycle_time_95th: number | null
  lead_time_85th: number | null
  current_wip: number
  flow_efficiency: number | null
  aging_wip_alerts: number
  item_types: string[]
}

export interface ThroughputPoint {
  week: string
  Total: number
  [key: string]: any
}

export interface ScatterPoint {
  item_key: string
  item_type: string
  completed_at: string
  cycle_time_days?: number
  lead_time_days?: number
}

export interface WipPoint {
  date: string
  stage: string
  count: number
}

export interface CfdPoint {
  date: string
  stage: string
  count: number
}

export interface AgingItem {
  item_key: string
  item_type: string
  stage: string
  age_days: number
  is_over_85th: boolean
  started_at: string | null
}

export interface MonteCarloResult {
  mode: 'when_done' | 'how_many'
  backlog_size?: number
  weeks?: number
  simulations: number
  percentiles: Record<string, string | number>
  histogram: Array<{ weeks?: number; items?: number; probability: number; cumulative: number }>
  recommended_date?: string
}

export interface WorkflowStepInput {
  position: number
  display_name: string
  source_statuses: string[]
  stage: 'queue' | 'start' | 'in_flight' | 'done'
}

export interface ProjectInput {
  name: string
  platform: Project['platform']
  config: Record<string, any>
  sync_frequency: 'hourly' | 'manual'
  workflow_steps: WorkflowStepInput[]
}

export interface ConnectionTest {
  success: boolean
  message: string
  projects_found: Array<{ id: string; name: string }>
}
