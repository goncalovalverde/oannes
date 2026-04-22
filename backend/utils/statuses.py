"""Workflow status constants and enums.

Centralized definitions of workflow statuses to avoid magic strings throughout the codebase.
These are the standard statuses used in Troy Magennis flow metrics.
"""

# Standard workflow statuses
STATUS_BACKLOG = "backlog"
STATUS_TODO = "todo"
STATUS_IN_PROGRESS = "in_progress"
STATUS_IN_REVIEW = "in_review"
STATUS_DONE = "done"
STATUS_CANCELLED = "cancelled"

# All valid statuses
ALL_STATUSES = [
    STATUS_BACKLOG,
    STATUS_TODO,
    STATUS_IN_PROGRESS,
    STATUS_IN_REVIEW,
    STATUS_DONE,
    STATUS_CANCELLED,
]

# Metrics calculation status mapping
# "completed" statuses are those where work is considered done
COMPLETED_STATUSES = {STATUS_DONE, STATUS_CANCELLED}

# "active" statuses are those where work is in progress
ACTIVE_STATUSES = {STATUS_TODO, STATUS_IN_PROGRESS, STATUS_IN_REVIEW}

# "waiting" statuses are those where work hasn't started
WAITING_STATUSES = {STATUS_BACKLOG}

# Sync job statuses
SYNC_STATUS_PENDING = "pending"
SYNC_STATUS_RUNNING = "running"
SYNC_STATUS_SUCCESS = "success"
SYNC_STATUS_ERROR = "error"

SYNC_STATUSES = [SYNC_STATUS_PENDING, SYNC_STATUS_RUNNING, SYNC_STATUS_SUCCESS, SYNC_STATUS_ERROR]
