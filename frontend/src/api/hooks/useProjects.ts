import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import client from '../client'
import type { Project, ProjectInput } from '../../types'
import { useToast } from '../../context/ToastContext'

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
  const { showToast } = useToast()
  
  return useMutation({
    mutationFn: (data: ProjectInput) => client.post('/projects/', data).then(r => r.data),
    onSuccess: (newProject) => {
      // Update cache immediately with new project
      qc.setQueryData(['projects'], (old: Project[] = []) => [...old, newProject])
      // Then refetch in background
      qc.invalidateQueries({ queryKey: ['projects'] })
      showToast(`Project "${newProject.name}" created successfully!`, 'success', 3000)
    },
    onError: (error: unknown) => {
      const msg = (error as { response?: { data?: { message?: string } } })?.response?.data?.message ?? 'Failed to create project'
      showToast(msg, 'error', 5000)
    },
  })
}

export function useUpdateProject() {
  const qc = useQueryClient()
  const { showToast } = useToast()
  
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ProjectInput }) =>
      client.put(`/projects/${id}`, data).then(r => r.data),
    onSuccess: (updatedProject) => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      showToast(`Project updated successfully!`, 'success', 3000)
    },
    onError: (error: unknown) => {
      const msg = (error as { response?: { data?: { message?: string } } })?.response?.data?.message ?? 'Failed to update project'
      showToast(msg, 'error', 5000)
    },
  })
}

export function useDeleteProject() {
  const qc = useQueryClient()
  const { showToast } = useToast()
  
  return useMutation({
    mutationFn: (id: number) => client.delete(`/projects/${id}`).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      showToast('Project deleted successfully!', 'success', 3000)
    },
    onError: (error: unknown) => {
      const msg = (error as { response?: { data?: { message?: string } } })?.response?.data?.message ?? 'Failed to delete project'
      showToast(msg, 'error', 5000)
    },
  })
}

export function useTestConnection() {
  const { showToast } = useToast()
  
  return useMutation({
    mutationFn: (data: { platform: string; config: Record<string, any> }) =>
      client.post('/connectors/test', data).then(r => r.data),
    onSuccess: () => {
      showToast('Connection successful!', 'success', 3000)
    },
    onError: (error: unknown) => {
      const msg = (error as { response?: { data?: { message?: string } } })?.response?.data?.message ?? 'Connection failed'
      showToast(msg, 'error', 5000)
    },
  })
}

export function useDiscoverStatuses() {
  const { showToast } = useToast()
  
  return useMutation({
    mutationFn: (data: { platform: string; config: Record<string, any>; board_id: string }) =>
      client.post('/connectors/discover-statuses', data).then(r => r.data),
    onError: (error: unknown) => {
      const msg = (error as { response?: { data?: { message?: string } } })?.response?.data?.message ?? 'Failed to discover statuses'
      showToast(msg, 'error', 5000)
    },
  })
}
