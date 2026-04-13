import { useQuery, useMutation } from '@tanstack/react-query'
import client from '../client'
import type { MetricsSummary, ThroughputPoint, ScatterPoint, WipPoint, CfdPoint, AgingItem, MonteCarloResult } from '../../types'

function metricsParams(weeks: number, itemType: string) {
  return { params: { weeks, item_type: itemType } }
}

export function useMetricsSummary(projectId: number | null, weeks: number, itemType: string) {
  return useQuery<MetricsSummary>({
    queryKey: ['metrics', projectId, 'summary', weeks, itemType],
    queryFn: () => client.get(`/metrics/${projectId}/summary`, metricsParams(weeks, itemType)).then(r => r.data),
    enabled: projectId != null,
  })
}

export function useThroughput(projectId: number | null, weeks: number, itemType: string) {
  return useQuery<ThroughputPoint[]>({
    queryKey: ['metrics', projectId, 'throughput', weeks, itemType],
    queryFn: () => client.get(`/metrics/${projectId}/throughput`, metricsParams(weeks, itemType)).then(r => r.data.data),
    enabled: projectId != null,
  })
}

export function useCycleTime(projectId: number | null, weeks: number, itemType: string) {
  return useQuery({
    queryKey: ['metrics', projectId, 'cycle-time', weeks, itemType],
    queryFn: () => client.get(`/metrics/${projectId}/cycle-time`, metricsParams(weeks, itemType)).then(r => r.data),
    enabled: projectId != null,
  })
}

export function useLeadTime(projectId: number | null, weeks: number, itemType: string) {
  return useQuery({
    queryKey: ['metrics', projectId, 'lead-time', weeks, itemType],
    queryFn: () => client.get(`/metrics/${projectId}/lead-time`, metricsParams(weeks, itemType)).then(r => r.data),
    enabled: projectId != null,
  })
}

export function useWip(projectId: number | null, weeks: number) {
  return useQuery<WipPoint[]>({
    queryKey: ['metrics', projectId, 'wip', weeks],
    queryFn: () => client.get(`/metrics/${projectId}/wip`, { params: { weeks } }).then(r => r.data.data),
    enabled: projectId != null,
  })
}

export function useCfd(projectId: number | null) {
  return useQuery<CfdPoint[]>({
    queryKey: ['metrics', projectId, 'cfd'],
    queryFn: () => client.get(`/metrics/${projectId}/cfd`).then(r => r.data.data),
    enabled: projectId != null,
  })
}

export function useAgingWip(projectId: number | null) {
  return useQuery<AgingItem[]>({
    queryKey: ['metrics', projectId, 'aging-wip'],
    queryFn: () => client.get(`/metrics/${projectId}/aging-wip`).then(r => r.data.data),
    enabled: projectId != null,
  })
}

export function useItemTypes(projectId: number | null) {
  return useQuery<string[]>({
    queryKey: ['metrics', projectId, 'item-types'],
    queryFn: () => client.get(`/metrics/${projectId}/item-types`).then(r => r.data.item_types),
    enabled: projectId != null,
  })
}

export function useRawData(projectId: number | null) {
  return useQuery({
    queryKey: ['metrics', projectId, 'raw'],
    queryFn: () => client.get(`/metrics/${projectId}/raw-data`).then(r => r.data.data),
    enabled: projectId != null,
  })
}

export function useMonteCarlo() {
  return useMutation<MonteCarloResult, Error, { project_id: number; backlog_size?: number; target_weeks?: number; simulations?: number; weeks_history?: number }>({
    mutationFn: (data) => client.post('/metrics/monte-carlo', data).then(r => r.data),
  })
}

export function useNetFlow(projectId: number | null, weeks: number, itemType: string) {
  return useQuery<{ week: string; arrivals: number; completions: number; net: number }[]>({
    queryKey: ['metrics', projectId, 'net-flow', weeks, itemType],
    queryFn: () =>
      client
        .get(`/metrics/${projectId}/net-flow`, { params: { weeks, item_type: itemType } })
        .then(r => r.data.data),
    enabled: projectId != null,
  })
}

export function useQualityRate(projectId: number | null, weeks: number, itemType: string) {
  return useQuery<{ week: string; total: number; bugs: number; quality_pct: number }[]>({
    queryKey: ['metrics', projectId, 'quality-rate', weeks, itemType],
    queryFn: () =>
      client
        .get(`/metrics/${projectId}/quality-rate`, { params: { weeks, item_type: itemType } })
        .then(r => r.data.data),
    enabled: projectId != null,
  })
}
