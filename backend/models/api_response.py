"""Standardized API response models for consistent, type-safe responses across all endpoints.

Every API endpoint should return a response that conforms to one of these models:
- ResponseEnvelope: Base response with status/error handling
- MetricDataResponse: For metric endpoints (throughput, cycle-time, etc.)
- ListResponse: For list endpoints (items, projects, etc.)
- SimpleResponse: For simple success/error responses

Benefits:
- Frontend can rely on consistent structure across all endpoints
- Clear error messages and status codes
- Type-safe response handling
- Better API documentation and discoverability
"""

from pydantic import BaseModel, Field
from typing import TypeVar, Generic, List, Optional, Dict, Any, Literal
from datetime import datetime
from enum import Enum


class ResponseStatus(str, Enum):
    """Response status values."""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"  # For partial failures in batch operations


T = TypeVar('T')


class ResponseEnvelope(BaseModel, Generic[T]):
    """Base response envelope for all API responses.
    
    Usage:
        {
            "status": "success",
            "data": {...},
            "timestamp": "2024-01-15T10:30:00Z"
        }
        
        {
            "status": "error",
            "error": {
                "code": "RATE_LIMIT",
                "message": "Rate limit exceeded. Retry after 30 seconds.",
                "retry_after_seconds": 30
            },
            "timestamp": "2024-01-15T10:30:00Z"
        }
    """
    
    status: ResponseStatus = Field(
        ...,
        description="Response status (success, error, or partial)"
    )
    data: Optional[T] = Field(
        None,
        description="Response data (null if status is error)"
    )
    error: Optional[Dict[str, Any]] = Field(
        None,
        description="Error details if status is error"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Response timestamp (UTC)"
    )
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() + 'Z' if v else None
        }


class MetricDataPoint(BaseModel):
    """Single data point in a metric time series."""
    
    date: str = Field(
        ...,
        description="Date or period (e.g., '2024-01-15' for daily, '2024-W03' for weekly)"
    )
    value: float = Field(
        ...,
        description="Metric value for this period"
    )
    by_type: Optional[Dict[str, Any]] = Field(
        None,
        description="Breakdown by item type or stage (optional). Values can be strings or integers."
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "date": "2024-01-15",
                "value": 42.5,
                "by_type": {"Feature": 20, "Bug": 15, "Enhancement": 7}
            }
        }


class MetricStats(BaseModel):
    """Statistical summary for a metric."""
    
    avg: float = Field(
        ...,
        description="Average value across time period"
    )
    min: Optional[float] = Field(
        None,
        description="Minimum value"
    )
    max: Optional[float] = Field(
        None,
        description="Maximum value"
    )
    p50: Optional[float] = Field(
        None,
        description="50th percentile (median)"
    )
    p75: Optional[float] = Field(
        None,
        description="75th percentile"
    )
    p85: Optional[float] = Field(
        None,
        description="85th percentile"
    )
    p95: Optional[float] = Field(
        None,
        description="95th percentile"
    )
    trend_pct: float = Field(
        0,
        description="Trend percentage (comparison of recent vs. older periods)"
    )


class MetricResponse(BaseModel):
    """Standardized response for metric endpoints (throughput, cycle-time, etc.).
    
    Usage:
        GET /api/metrics/{project_id}/throughput?weeks=12
        
        {
            "data": [
                {"date": "2024-01-01", "value": 42},
                {"date": "2024-01-08", "value": 38}
            ],
            "stats": {
                "avg": 40.5,
                "min": 30,
                "max": 50,
                "p50": 40,
                "trend_pct": 5.2
            },
            "unit": "items/week",
            "period": "weekly"
        }
    """
    
    data: List[MetricDataPoint] = Field(
        ...,
        description="Time series data points"
    )
    stats: MetricStats = Field(
        ...,
        description="Statistical summary"
    )
    unit: str = Field(
        ...,
        description="Unit of measurement (e.g., 'items/week', 'days', '%')"
    )
    period: str = Field(
        ...,
        description="Time period granularity (daily, weekly, monthly)"
    )


class ListItem(BaseModel):
    """Item in a list response."""
    
    id: int = Field(
        ...,
        description="Item ID"
    )
    name: str = Field(
        ...,
        description="Item name or display text"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional item metadata"
    )


class ListResponse(BaseModel):
    """Standardized response for list endpoints.
    
    Usage:
        GET /api/projects
        
        {
            "items": [
                {"id": 1, "name": "Project A"},
                {"id": 2, "name": "Project B"}
            ],
            "total": 2,
            "offset": 0,
            "limit": 50
        }
    """
    
    items: List[ListItem] = Field(
        ...,
        description="List of items"
    )
    total: int = Field(
        ...,
        description="Total count of items (across all pages)"
    )
    offset: int = Field(
        0,
        description="Pagination offset"
    )
    limit: int = Field(
        50,
        description="Pagination limit"
    )


class SimpleResponse(BaseModel):
    """Standardized response for simple success/error operations.
    
    Usage:
        POST /api/projects/{id}/sync
        
        {
            "message": "Sync started successfully",
            "data": {"sync_job_id": 123}
        }
    """
    
    message: str = Field(
        ...,
        description="Human-readable message"
    )
    data: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional additional data"
    )


class ErrorDetail(BaseModel):
    """Detailed error information."""
    
    code: str = Field(
        ...,
        description="Error code (e.g., 'INVALID_CONFIG', 'RATE_LIMIT', 'NOT_FOUND')"
    )
    message: str = Field(
        ...,
        description="Human-readable error message"
    )
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional error details"
    )
    retry_after_seconds: Optional[int] = Field(
        None,
        description="Seconds to wait before retrying (if applicable)"
    )
    documentation_url: Optional[str] = Field(
        None,
        description="URL to documentation for this error"
    )


def create_success_response(data: T, timestamp: Optional[datetime] = None) -> ResponseEnvelope[T]:
    """Create a successful response envelope.
    
    Args:
        data: Response data
        timestamp: Optional response timestamp (defaults to now)
        
    Returns:
        ResponseEnvelope with status=success
    """
    return ResponseEnvelope(
        status=ResponseStatus.SUCCESS,
        data=data,
        timestamp=timestamp or datetime.utcnow()
    )


def create_error_response(
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    retry_after_seconds: Optional[int] = None,
    timestamp: Optional[datetime] = None
) -> ResponseEnvelope:
    """Create an error response envelope.
    
    Args:
        code: Error code
        message: Human-readable message
        details: Optional error details
        retry_after_seconds: Optional retry-after delay
        timestamp: Optional response timestamp (defaults to now)
        
    Returns:
        ResponseEnvelope with status=error
    """
    error_dict = {
        "code": code,
        "message": message
    }
    
    if details:
        error_dict["details"] = details
    
    if retry_after_seconds:
        error_dict["retry_after_seconds"] = retry_after_seconds
    
    return ResponseEnvelope(
        status=ResponseStatus.ERROR,
        error=error_dict,
        timestamp=timestamp or datetime.utcnow()
    )


class MetricsSummary(BaseModel):
    """Dashboard summary — aggregates all key flow metrics in a single response."""
    throughput_avg: float
    throughput_trend_pct: float
    cycle_time_avg: Optional[float]
    cycle_time_50th: Optional[float]
    cycle_time_85th: Optional[float]
    cycle_time_95th: Optional[float]
    lead_time_85th: Optional[float]
    current_wip: int
    flow_efficiency: float
    aging_wip_alerts: int
    item_types: List[str]
