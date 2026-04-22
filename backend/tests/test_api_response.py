"""Tests for standardized API response models."""

import pytest
from datetime import datetime, timezone
from models.api_response import (
    ResponseEnvelope, ResponseStatus, MetricResponse, MetricDataPoint, MetricStats,
    ListResponse, ListItem, SimpleResponse, ErrorDetail,
    create_success_response, create_error_response
)
import json


class TestResponseEnvelope:
    """Test base response envelope."""
    
    def test_success_response_envelope(self):
        """Should create successful response envelope."""
        envelope = ResponseEnvelope(
            status=ResponseStatus.SUCCESS,
            data={"key": "value"}
        )
        assert envelope.status == ResponseStatus.SUCCESS
        assert envelope.data == {"key": "value"}
        assert envelope.error is None
        assert envelope.timestamp is not None
    
    def test_error_response_envelope(self):
        """Should create error response envelope."""
        envelope = ResponseEnvelope(
            status=ResponseStatus.ERROR,
            error={
                "code": "NOT_FOUND",
                "message": "Project not found"
            }
        )
        assert envelope.status == ResponseStatus.ERROR
        assert envelope.data is None
        assert envelope.error["code"] == "NOT_FOUND"
    
    def test_response_envelope_json_serialization(self):
        """Should serialize to JSON with timestamp in ISO format."""
        envelope = ResponseEnvelope(
            status=ResponseStatus.SUCCESS,
            data={"id": 1}
        )
        json_str = envelope.model_dump_json()
        data = json.loads(json_str)
        
        assert data["status"] == "success"
        assert data["data"]["id"] == 1
        assert "timestamp" in data


class TestMetricResponse:
    """Test metric response model."""
    
    def test_metric_response(self):
        """Should create valid metric response."""
        response = MetricResponse(
            data=[
                MetricDataPoint(date="2024-01-01", value=42),
                MetricDataPoint(date="2024-01-08", value=38)
            ],
            stats=MetricStats(
                avg=40,
                min=30,
                max=50,
                trend_pct=5.2
            ),
            unit="items/week",
            period="weekly"
        )
        
        assert len(response.data) == 2
        assert response.data[0].date == "2024-01-01"
        assert response.stats.avg == 40
        assert response.unit == "items/week"
    
    def test_metric_data_point_with_breakdown(self):
        """MetricDataPoint should include breakdown by type."""
        point = MetricDataPoint(
            date="2024-01-01",
            value=42,
            by_type={"Feature": 20, "Bug": 15, "Enhancement": 7}
        )
        assert point.by_type["Feature"] == 20
    
    def test_metric_stats_with_percentiles(self):
        """MetricStats should include percentile data."""
        stats = MetricStats(
            avg=40,
            min=30,
            max=50,
            p50=40,
            p75=45,
            p95=48
        )
        assert stats.p50 == 40
        assert stats.p95 == 48


class TestListResponse:
    """Test list response model."""
    
    def test_list_response(self):
        """Should create valid list response."""
        response = ListResponse(
            items=[
                ListItem(id=1, name="Project A"),
                ListItem(id=2, name="Project B")
            ],
            total=10,
            offset=0,
            limit=2
        )
        
        assert len(response.items) == 2
        assert response.total == 10
        assert response.offset == 0
        assert response.limit == 2
    
    def test_list_item_with_metadata(self):
        """ListItem should include optional metadata."""
        item = ListItem(
            id=1,
            name="Project A",
            metadata={"status": "active", "created_at": "2024-01-01"}
        )
        assert item.metadata["status"] == "active"


class TestSimpleResponse:
    """Test simple response model."""
    
    def test_simple_response(self):
        """Should create valid simple response."""
        response = SimpleResponse(
            message="Operation completed successfully",
            data={"operation_id": 123}
        )
        assert response.message == "Operation completed successfully"
        assert response.data["operation_id"] == 123


class TestErrorDetail:
    """Test error detail model."""
    
    def test_error_detail_minimal(self):
        """Should create error detail with code and message."""
        error = ErrorDetail(
            code="NOT_FOUND",
            message="Project not found"
        )
        assert error.code == "NOT_FOUND"
        assert error.message == "Project not found"
    
    def test_error_detail_with_retry(self):
        """Should include retry_after_seconds for rate limit errors."""
        error = ErrorDetail(
            code="RATE_LIMIT",
            message="Rate limit exceeded",
            retry_after_seconds=30
        )
        assert error.retry_after_seconds == 30
    
    def test_error_detail_with_documentation(self):
        """Should include documentation URL."""
        error = ErrorDetail(
            code="INVALID_CONFIG",
            message="Invalid configuration",
            documentation_url="https://docs.example.com/config"
        )
        assert error.documentation_url == "https://docs.example.com/config"


class TestHelperFunctions:
    """Test helper functions for creating responses."""
    
    def test_create_success_response(self):
        """Should create success envelope with helper."""
        response = create_success_response({"id": 1, "name": "Test"})
        
        assert response.status == ResponseStatus.SUCCESS
        assert response.data["id"] == 1
        assert response.error is None
    
    def test_create_error_response(self):
        """Should create error envelope with helper."""
        response = create_error_response(
            code="NOT_FOUND",
            message="Project not found"
        )
        
        assert response.status == ResponseStatus.ERROR
        assert response.error["code"] == "NOT_FOUND"
        assert response.error["message"] == "Project not found"
        assert response.data is None
    
    def test_create_error_response_with_retry(self):
        """Should include retry_after in error response."""
        response = create_error_response(
            code="RATE_LIMIT",
            message="Rate limit exceeded",
            retry_after_seconds=60
        )
        
        assert response.error["retry_after_seconds"] == 60
    
    def test_create_error_response_with_details(self):
        """Should include details dict in error response."""
        response = create_error_response(
            code="VALIDATION_ERROR",
            message="Invalid input",
            details={"field": "email", "reason": "invalid format"}
        )
        
        assert response.error["details"]["field"] == "email"


class TestResponseSerialization:
    """Test JSON serialization of responses."""
    
    def test_metric_response_serialization(self):
        """Should serialize metric response to JSON."""
        response = MetricResponse(
            data=[MetricDataPoint(date="2024-01-01", value=42)],
            stats=MetricStats(avg=40, trend_pct=5.2),
            unit="items/week",
            period="weekly"
        )
        json_str = response.model_dump_json()
        data = json.loads(json_str)
        
        assert data["unit"] == "items/week"
        assert data["data"][0]["date"] == "2024-01-01"
        assert data["stats"]["avg"] == 40
    
    def test_list_response_serialization(self):
        """Should serialize list response to JSON."""
        response = ListResponse(
            items=[ListItem(id=1, name="Item 1")],
            total=1,
            offset=0,
            limit=50
        )
        json_str = response.model_dump_json()
        data = json.loads(json_str)
        
        assert len(data["items"]) == 1
        assert data["total"] == 1
    
    def test_envelope_timestamp_format(self):
        """Should serialize timestamp in ISO format."""
        response = create_success_response({"test": "data"})
        json_str = response.model_dump_json()
        data = json.loads(json_str)
        
        # Check timestamp is in ISO format (contains 'T' and either 'Z' or timezone offset)
        timestamp = data["timestamp"]
        assert "T" in timestamp
        assert timestamp.endswith("Z") or "+" in timestamp or "-" in timestamp


class TestResponseTypes:
    """Test different response status types."""
    
    def test_response_status_enum(self):
        """Should have correct response status values."""
        assert ResponseStatus.SUCCESS.value == "success"
        assert ResponseStatus.ERROR.value == "error"
        assert ResponseStatus.PARTIAL.value == "partial"
    
    def test_partial_response_status(self):
        """Should support partial failure responses."""
        response = ResponseEnvelope(
            status=ResponseStatus.PARTIAL,
            data={"successful": 8, "failed": 2},
            error={"message": "Some items failed"}
        )
        assert response.status == ResponseStatus.PARTIAL
