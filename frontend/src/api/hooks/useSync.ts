import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import client from '../client'
import type { SyncJob } from '../../types'

export function useSyncStatus(projectId: number | null) {
  return useQuery<SyncJob>({
    queryKey: ['sync', projectId, 'status'],
    queryFn: () => client.get(`/sync/${projectId}/status`).then(r => r.data),
    enabled: projectId != null,
    refetchInterval: (query) => {
      const d = query.state.data
      return d?.status === 'running' || d?.status === 'pending' ? 2000 : false
    },
  })
}

export function useTriggerSync() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (projectId: number) => client.post(`/sync/${projectId}`).then(r => r.data),
    onSuccess: (_data, projectId) => {
      qc.invalidateQueries({ queryKey: ['sync', projectId] })
      qc.invalidateQueries({ queryKey: ['projects'] })
      qc.invalidateQueries({ queryKey: ['metrics', projectId] })
    },
  })
}
