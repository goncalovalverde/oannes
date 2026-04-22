import { useState, useEffect } from 'react'
import client from '../api/client'

interface PerformanceMetrics {
  total_syncs: number
  successful_syncs: number
  failed_syncs: number
  avg_items_fetched: number | null
  avg_sync_duration_seconds: number | null
  last_sync_status: string | null
  last_sync_at: string | null
  last_sync_duration_seconds: number | null
}

interface PerformanceMonitoringProps {
  projectId: number
}

export function PerformanceMonitoring({ projectId }: PerformanceMonitoringProps) {
  const [metrics, setMetrics] = useState<PerformanceMetrics | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const loadMetrics = async () => {
      try {
        setIsLoading(true)
        const res = await client.get(`/api/sync/${projectId}/performance-metrics`)
        setMetrics(res.data)
        setError(null)
      } catch (err) {
        console.error('Failed to load performance metrics:', err)
        setError('Failed to load metrics')
      } finally {
        setIsLoading(false)
      }
    }

    loadMetrics()
    // Refresh metrics every 30 seconds
    const interval = setInterval(loadMetrics, 30000)
    return () => clearInterval(interval)
  }, [projectId])

  if (isLoading || !metrics) {
    return (
      <div className="p-6 bg-surface rounded-lg border border-border">
        <div className="text-sm text-muted">Loading metrics...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 bg-surface rounded-lg border border-border">
        <div className="text-sm text-danger">{error}</div>
      </div>
    )
  }

  const successRate = metrics.total_syncs > 0 
    ? ((metrics.successful_syncs / metrics.total_syncs) * 100).toFixed(1)
    : 'N/A'

  const formatDuration = (seconds: number | null) => {
    if (seconds === null) return 'N/A'
    if (seconds < 60) return `${Math.round(seconds)}s`
    return `${(seconds / 60).toFixed(1)}m`
  }

  const lastSyncDate = metrics.last_sync_at ? new Date(metrics.last_sync_at) : null

  return (
    <div className="space-y-4 p-6 bg-surface rounded-lg border border-border">
      <div>
        <h3 className="text-sm font-semibold text-text mb-2">Performance Metrics</h3>
        <p className="text-xs text-muted2">Sync performance statistics for this project (last 10 syncs)</p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Success Rate */}
        <div className="p-4 bg-surface2 rounded-lg border border-border">
          <div className="text-xs font-semibold text-muted uppercase tracking-widest mb-1">Success Rate</div>
          <div className="text-2xl font-bold text-primary">{successRate}%</div>
          <div className="text-xs text-muted2 mt-1">
            {metrics.successful_syncs}/{metrics.total_syncs} successful
          </div>
        </div>

        {/* Average Sync Duration */}
        <div className="p-4 bg-surface2 rounded-lg border border-border">
          <div className="text-xs font-semibold text-muted uppercase tracking-widest mb-1">Avg Duration</div>
          <div className="text-2xl font-bold text-primary">{formatDuration(metrics.avg_sync_duration_seconds)}</div>
          <div className="text-xs text-muted2 mt-1">Per sync</div>
        </div>

        {/* Total Syncs */}
        <div className="p-4 bg-surface2 rounded-lg border border-border">
          <div className="text-xs font-semibold text-muted uppercase tracking-widest mb-1">Total Syncs</div>
          <div className="text-2xl font-bold text-primary">{metrics.total_syncs}</div>
          <div className="text-xs text-muted2 mt-1">
            <span className="text-danger">{metrics.failed_syncs}</span> failed
          </div>
        </div>

        {/* Average Items */}
        <div className="p-4 bg-surface2 rounded-lg border border-border">
          <div className="text-xs font-semibold text-muted uppercase tracking-widest mb-1">Avg Items</div>
          <div className="text-2xl font-bold text-primary">
            {metrics.avg_items_fetched ? Math.round(metrics.avg_items_fetched) : 'N/A'}
          </div>
          <div className="text-xs text-muted2 mt-1">Per sync</div>
        </div>
      </div>

      {/* Last Sync Info */}
      {metrics.last_sync_at && (
        <div className="pt-4 border-t border-border">
          <div className="text-xs font-semibold text-muted uppercase tracking-widest mb-3">Last Sync</div>
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-xs text-muted2">Status</span>
              <span className={`text-xs font-medium px-2 py-1 rounded ${
                metrics.last_sync_status === 'completed' 
                  ? 'bg-green-100 text-green-700' 
                  : metrics.last_sync_status === 'failed'
                  ? 'bg-red-100 text-red-700'
                  : 'bg-yellow-100 text-yellow-700'
              }`}>
                {metrics.last_sync_status?.toUpperCase()}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs text-muted2">Duration</span>
              <span className="text-xs font-medium">{formatDuration(metrics.last_sync_duration_seconds)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs text-muted2">Time</span>
              <span className="text-xs font-medium">
                {lastSyncDate?.toLocaleString() || 'N/A'}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
