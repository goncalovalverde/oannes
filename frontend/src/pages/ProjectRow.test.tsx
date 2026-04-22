/**
 * Tests for Projects page.
 *
 * Strategy: Test that ProjectRow correctly uses hooks without violation,
 * and that project creation properly updates the cache.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import ProjectRow from './ProjectRow'
import type { Project } from '../types'

// Mock the sync hooks
const mockTriggerSync = vi.fn()
const mockClearCache = vi.fn()
vi.mock('../api/hooks/useSync', () => ({
  useSyncStatus: vi.fn(() => ({
    data: { status: 'idle', items_fetched: 0 },
  })),
  useTriggerSync: vi.fn(() => ({
    mutate: mockTriggerSync,
  })),
  useClearCache: vi.fn(() => ({
    mutate: mockClearCache,
  })),
}))

const mockProject: Project = {
  id: 1,
  name: 'Test Project',
  platform: 'jira',
  config: { url: 'https://test.atlassian.net', auth_type: 'api_token' },
  workflow_steps: [],
  created_at: new Date().toISOString(),
  last_synced_at: null,
}

function renderProjectRow(project = mockProject) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ProjectRow
          project={project}
          onEdit={vi.fn()}
          onDelete={vi.fn()}
        />
      </BrowserRouter>
    </QueryClientProvider>
  )
}

describe('ProjectRow — Hook Rules Compliance', () => {
  beforeEach(() => {
    mockTriggerSync.mockClear()
    mockClearCache.mockClear()
  })

  it('renders without violating rules of hooks', () => {
    // This test passes if render() doesn't throw about invalid hook calls
    expect(() => renderProjectRow()).not.toThrow()
  })

  it('displays project name', () => {
    renderProjectRow()
    expect(screen.getByText('Test Project')).toBeInTheDocument()
  })

  it('displays platform label', () => {
    renderProjectRow()
    expect(screen.getByText('Jira')).toBeInTheDocument()
  })

  it('has sync, edit, delete, and reset cache buttons', () => {
    renderProjectRow()
    expect(screen.getByText('↻ Sync Now')).toBeInTheDocument()
    expect(screen.getByText('✏ Edit')).toBeInTheDocument()
    expect(screen.getByText('🔄 Reset Cache')).toBeInTheDocument()
    expect(screen.getByText('🗑 Delete')).toBeInTheDocument()
  })

  it('calls onEdit when edit button is clicked', async () => {
    const onEdit = vi.fn()
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ProjectRow
            project={mockProject}
            onEdit={onEdit}
            onDelete={vi.fn()}
          />
        </BrowserRouter>
      </QueryClientProvider>
    )

    await userEvent.click(screen.getByText('✏ Edit'))
    expect(onEdit).toHaveBeenCalledWith(mockProject)
  })

  it('calls onDelete when delete button is clicked and confirmed', async () => {
    const onDelete = vi.fn()
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })

    vi.spyOn(window, 'confirm').mockReturnValue(true)

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ProjectRow
            project={mockProject}
            onEdit={vi.fn()}
            onDelete={onDelete}
          />
        </BrowserRouter>
      </QueryClientProvider>
    )

    await userEvent.click(screen.getByText('🗑 Delete'))
    expect(onDelete).toHaveBeenCalledWith(mockProject.id)
  })

  it('calls triggerSync when sync button is clicked', async () => {
    renderProjectRow()
    await userEvent.click(screen.getByText('↻ Sync Now'))
    expect(mockTriggerSync).toHaveBeenCalledWith(mockProject.id)
  })

  it('calls clearCache when reset cache button is clicked and confirmed', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })

    vi.spyOn(window, 'confirm').mockReturnValue(true)

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ProjectRow
            project={mockProject}
            onEdit={vi.fn()}
            onDelete={vi.fn()}
          />
        </BrowserRouter>
      </QueryClientProvider>
    )

    await userEvent.click(screen.getByText('🔄 Reset Cache'))
    expect(mockClearCache).toHaveBeenCalledWith(mockProject.id)
  })
})
