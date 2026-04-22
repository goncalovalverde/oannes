import { useState, useEffect } from 'react'
import { useToast } from '../context/ToastContext'
import AlertBanner from './ui/AlertBanner'
import client from '../api/client'

interface ProjectSettingsProps {
  projectId: number
  onClose?: () => void
}

interface RateLimitConfig {
  enabled: boolean
  retry_delay_seconds: number
}

export function ProjectSettings({ projectId, onClose }: ProjectSettingsProps) {
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [rateLimitEnabled, setRateLimitEnabled] = useState(false)
  const [retryDelay, setRetryDelay] = useState(5)
  const { showToast } = useToast()

  // Load current rate-limit config
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const res = await client.get(`/api/sync/${projectId}/rate-limit-config`)
        const config: RateLimitConfig = res.data
        setRateLimitEnabled(config.enabled)
        setRetryDelay(config.retry_delay_seconds)
      } catch (err) {
        console.error('Failed to load rate-limit config:', err)
        showToast('Failed to load settings', 'error', 3000)
      } finally {
        setIsLoading(false)
      }
    }
    loadConfig()
  }, [projectId, showToast])

  const handleSave = async () => {
    setIsSaving(true)
    try {
      await client.put(`/api/sync/${projectId}/rate-limit-config`, {
        enabled: rateLimitEnabled,
        retry_delay_seconds: retryDelay,
      })
      showToast('Rate limit settings saved', 'success', 3000)
      onClose?.()
    } catch (err) {
      console.error('Failed to save rate-limit config:', err)
      showToast('Failed to save settings', 'error', 3000)
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoading) {
    return (
      <div className="p-6 bg-surface rounded-lg border border-border">
        <div className="text-sm text-muted">Loading settings...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6 p-6 bg-surface rounded-lg border border-border max-w-md">
      <div>
        <h3 className="text-sm font-semibold text-text mb-4">Rate Limiting Configuration</h3>
        <p className="text-xs text-muted2 mb-6">
          Configure how the system handles API rate limits when syncing data from external platforms.
        </p>
      </div>

      <div className="space-y-4">
        <div>
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={rateLimitEnabled}
              onChange={(e) => setRateLimitEnabled(e.target.checked)}
              className="w-4 h-4 rounded border-border"
            />
            <span className="text-sm font-medium text-text">Enable automatic retry on rate limit</span>
          </label>
          <p className="text-xs text-muted2 mt-1 ml-7">
            When enabled, the sync will automatically retry after the specified delay when the API returns a rate limit error.
          </p>
        </div>

        {rateLimitEnabled && (
          <div className="pl-7 pt-3 border-l-2 border-primary/30">
            <label className="block text-xs font-semibold text-muted uppercase tracking-widest mb-2">
              Retry Delay (seconds)
            </label>
            <input
              type="number"
              min="1"
              max="300"
              step="1"
              value={retryDelay}
              onChange={(e) => setRetryDelay(Math.max(1, parseInt(e.target.value) || 5))}
              className="w-full bg-surface2 border border-border text-text text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-primary"
            />
            <p className="text-xs text-muted2 mt-1">
              Default: 5 seconds. The system will wait this long before retrying (up to 3 attempts).
            </p>
          </div>
        )}
      </div>

      <AlertBanner type="info">
        <div className="text-xs">
          💡 <strong>Tip:</strong> Jira Cloud typically returns rate limits after 10 requests per second. If you have many issues, increase the delay to 2-5 seconds between requests.
        </div>
      </AlertBanner>

      <div className="flex gap-3 pt-4 border-t border-border">
        <button
          onClick={onClose}
          className="flex-1 px-4 py-2 text-sm font-medium text-muted2 hover:text-text rounded-lg border border-border transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={handleSave}
          disabled={isSaving}
          className="flex-1 px-4 py-2 text-sm font-medium text-white bg-primary hover:bg-primary/90 rounded-lg disabled:opacity-50 transition-colors"
        >
          {isSaving ? 'Saving...' : 'Save'}
        </button>
      </div>
    </div>
  )
}
