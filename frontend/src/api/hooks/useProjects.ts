import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import client from '../client'
import type { Project, ProjectInput } from '../../types'

export function useProjects() {
  return useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: () => client.get('/projects/').then(r => r.data),
  })
}

export function useProject(id: number | null) {
  return useQuery<Project>({
    queryKey: ['projects', id],
    queryFn: () => client.get(`/projects/${id}`).then(r => r.data),
    enabled: id != null,
  })
}

export function useCreateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: ProjectInput) => client.post('/projects/', data).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
  })
}

export function useUpdateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ProjectInput }) =>
      client.put(`/projects/${id}`, data).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
  })
}

export function useDeleteProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => client.delete(`/projects/${id}`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
  })
}

export function useTestConnection() {
  return useMutation({
    mutationFn: (data: { platform: string; config: Record<string, any> }) =>
      client.post('/connectors/test', data).then(r => r.data),
  })
}

export function useDiscoverStatuses() {
  return useMutation({
    mutationFn: (data: { platform: string; config: Record<string, any>; board_id: string }) =>
      client.post('/connectors/discover-statuses', data).then(r => r.data),
  })
}
