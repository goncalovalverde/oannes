import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import client from '../client'
import type { SyncJob } from '../../types'
import { useToast } from '../../context/ToastContext'

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
  const { showToast } = useToast()
  
  return useMutation({
    mutationFn: (projectId: number) => client.post(`/sync/${projectId}`).then(r => r.data),
    onSuccess: (newSyncJob, projectId) => {
      qc.setQueryData(['sync', projectId, 'status'], newSyncJob)
      qc.invalidateQueries({ queryKey: ['sync', projectId] })
      qc.invalidateQueries({ queryKey: ['projects'] })
      qc.invalidateQueries({ queryKey: ['metrics', projectId] })
      showToast('Sync started...', 'info', 2000)
    },
    onError: (error: unknown) => {
      const msg = (error as { response?: { data?: { message?: string } } })?.response?.data?.message ?? 'Failed to start sync'
      showToast(msg, 'error', 5000)
    },
  })
}

export function useCsvUploadSync() {
  const qc = useQueryClient()
  const { showToast } = useToast()
  
  return useMutation({
    mutationFn: ({ projectId, file }: { projectId: number; file: File }) => {
      const form = new FormData()
      form.append('file', file)
      return client.post(`/sync/${projectId}/csv-upload`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      }).then(r => r.data)
    },
    onSuccess: (newSyncJob, { projectId }) => {
      qc.setQueryData(['sync', projectId, 'status'], newSyncJob)
      qc.invalidateQueries({ queryKey: ['sync', projectId] })
      qc.invalidateQueries({ queryKey: ['projects'] })
      qc.invalidateQueries({ queryKey: ['metrics', projectId] })
      showToast('CSV uploaded and synced successfully!', 'success', 3000)
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { message?: string; detail?: string } } })?.response?.data?.message 
        ?? (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail 
        ?? 'CSV upload failed'
      showToast(msg, 'error', 5000)
    },
  })
}

export function useClearCache() {
  const qc = useQueryClient()
  const { showToast } = useToast()
  
  return useMutation({
    mutationFn: (projectId: number) => client.delete(`/sync/${projectId}/cache`).then(r => r.data),
    onSuccess: (_result, projectId) => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      qc.invalidateQueries({ queryKey: ['metrics', projectId] })
      showToast('Cache cleared. Next sync will fetch all items.', 'info', 3000)
    },
    onError: (error: unknown) => {
      const msg = (error as { response?: { data?: { message?: string } } })?.response?.data?.message ?? 'Failed to clear cache'
      showToast(msg, 'error', 5000)
    },
  })
}
