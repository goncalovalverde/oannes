/**
 * Tests for ProjectWizard component.
 *
 * Strategy: mock all API hooks so tests run without a network or server.
 * We test user-observable behaviour: rendering, navigation, and form logic.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ProjectWizard from './ProjectWizard'

// ---------------------------------------------------------------------------
// Mock all API hooks — they call the server and are tested separately
// ---------------------------------------------------------------------------
vi.mock('../../api/hooks/useProjects', () => ({
  useCreateProject:    () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateProject:    () => ({ mutate: vi.fn(), isPending: false }),
  useTestConnection:   () => ({ mutate: vi.fn(), isPending: false }),
  useDiscoverStatuses: () => ({ mutate: vi.fn() }),
}))

// ---------------------------------------------------------------------------
// Shared props
// ---------------------------------------------------------------------------
const defaultProps = {
  onClose: vi.fn(),
  onSaved: vi.fn(),
}

function renderWizard(props = {}) {
  return render(<ProjectWizard {...defaultProps} {...props} />)
}

// ---------------------------------------------------------------------------
// Step 1 — Platform selection
// ---------------------------------------------------------------------------

describe('ProjectWizard — Step 1: Platform selection', () => {
  beforeEach(() => {
    defaultProps.onClose.mockClear()
    defaultProps.onSaved.mockClear()
  })

  it('renders "New Project" title on first open', () => {
    renderWizard()
    expect(screen.getByText('New Project')).toBeInTheDocument()
  })

  it('renders step indicator "Step 1 of 3"', () => {
    renderWizard()
    expect(screen.getByText(/Step 1 of 3/i)).toBeInTheDocument()
  })

  it('shows all enabled platform buttons', () => {
    renderWizard()
    expect(screen.getByText('Jira')).toBeInTheDocument()
    expect(screen.getByText('Trello')).toBeInTheDocument()
    expect(screen.getByText('Azure DevOps')).toBeInTheDocument()
    expect(screen.getByText('GitLab')).toBeInTheDocument()
    expect(screen.getByText('CSV / Excel')).toBeInTheDocument()
  })

  it('Next button is disabled when no platform is selected', () => {
    renderWizard()
    const next = screen.getByRole('button', { name: /next/i })
    expect(next).toBeDisabled()
  })

  it('Next button enables after selecting a platform', async () => {
    renderWizard()
    await userEvent.click(screen.getByText('CSV / Excel'))
    const next = screen.getByRole('button', { name: /next/i })
    expect(next).not.toBeDisabled()
  })

  it('clicking Next advances to Step 2', async () => {
    renderWizard()
    await userEvent.click(screen.getByText('Jira'))
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByText(/Step 2 of 3/i)).toBeInTheDocument()
  })

  it('close button calls onClose', async () => {
    renderWizard()
    await userEvent.click(screen.getByRole('button', { name: '×' }))
    expect(defaultProps.onClose).toHaveBeenCalledOnce()
  })

  it('disabled platforms (Linear, Shortcut) cannot be clicked to advance', async () => {
    renderWizard()
    const linearBtn = screen.getByText('Linear').closest('button')!
    expect(linearBtn).toBeDisabled()
  })
})

// ---------------------------------------------------------------------------
// Step 2 — Credentials
// ---------------------------------------------------------------------------

describe('ProjectWizard — Step 2: Credentials', () => {
  async function goToStep2(platform = 'Jira') {
    renderWizard()
    await userEvent.click(screen.getByText(platform))
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
  }

  it('shows project name field on Step 2', async () => {
    await goToStep2()
    expect(screen.getByPlaceholderText('My Team')).toBeInTheDocument()
  })

  it('shows Jira-specific fields when Jira platform selected', async () => {
    await goToStep2('Jira')
    expect(screen.getByPlaceholderText('https://yourcompany.atlassian.net')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('you@company.com')).toBeInTheDocument()
  })

  it('shows CSV file path field when CSV platform selected', async () => {
    await goToStep2('CSV / Excel')
    expect(screen.getByPlaceholderText('/path/to/data.csv')).toBeInTheDocument()
  })

  it('Test Connection button is visible', async () => {
    await goToStep2()
    expect(screen.getByRole('button', { name: /test connection/i })).toBeInTheDocument()
  })

  it('typing in the project name field updates it', async () => {
    await goToStep2()
    const nameInput = screen.getByPlaceholderText('My Team')
    await userEvent.type(nameInput, 'My Team Alpha')
    expect(nameInput).toHaveValue('My Team Alpha')
  })
})

// ---------------------------------------------------------------------------
// Edit mode
// ---------------------------------------------------------------------------

describe('ProjectWizard — Edit mode', () => {
  const existingProject = {
    id: 42,
    name: 'Existing Project',
    platform: 'jira' as const,
    config: { url: 'https://jira.test', email: 'dev@test.com', api_token: 'tok' },
    last_synced_at: null,
    created_at: '2025-01-01T00:00:00',
    workflow_steps: [],
  }

  it('shows "Edit Project" title in edit mode', () => {
    renderWizard({ existing: existingProject })
    expect(screen.getByText('Edit Project')).toBeInTheDocument()
  })

  it('starts on Step 2 (credentials) when editing', () => {
    renderWizard({ existing: existingProject })
    expect(screen.getByText(/Step 2 of 3/i)).toBeInTheDocument()
  })

  it('pre-fills project name from existing project', () => {
    renderWizard({ existing: existingProject })
    expect(screen.getByDisplayValue('Existing Project')).toBeInTheDocument()
  })
})
