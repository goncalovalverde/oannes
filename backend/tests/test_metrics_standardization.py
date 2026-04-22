"""Tests for metrics API standardization with ResponseEnvelope."""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime
import json


def test_throughput_response_structure(client, sample_project):
    """Throughput endpoint should return ResponseEnvelope[MetricResponse]."""
    response = client.get(f"/api/metrics/{sample_project.id}/throughput?weeks=4")
    assert response.status_code == 200
    
    data = response.json()
    
    # Check envelope structure
    assert "status" in data
    assert data["status"] == "success"
    assert "data" in data
    assert "timestamp" in data
    
    # Check MetricResponse structure
    metric = data["data"]
    assert "data" in metric  # Time series data
    assert "stats" in metric
    assert "unit" in metric
    assert "period" in metric
    
    # Check stats structure
    stats = metric["stats"]
    assert "avg" in stats
    assert "trend_pct" in stats


def test_cycle_time_response_structure(client, sample_project):
    """Cycle time endpoint should return ResponseEnvelope[MetricResponse]."""
    response = client.get(f"/api/metrics/{sample_project.id}/cycle-time?weeks=4")
    assert response.status_code == 200
    
    data = response.json()
    
    # Check envelope structure
    assert data["status"] == "success"
    assert "data" in data
    assert "timestamp" in data
    
    # Check MetricResponse structure
    metric = data["data"]
    assert "data" in metric
    assert "stats" in metric
    assert metric["unit"] == "days"
    assert metric["period"] == "individual"
    
    # Check stats includes percentiles (may be None if no data)
    stats = metric["stats"]
    assert "avg" in stats
    # These are optional and may be None
    assert "p50" in stats or "p85" in stats or "p95" in stats


def test_cycle_time_interval_response_structure(client, sample_project):
    """Cycle time interval endpoint should return ResponseEnvelope[MetricResponse]."""
    response = client.get(f"/api/metrics/{sample_project.id}/cycle-time-interval?weeks=4&granularity=week")
    assert response.status_code == 200
    
    data = response.json()
    
    # Check envelope structure
    assert data["status"] == "success"
    
    # Check MetricResponse structure
    metric = data["data"]
    assert metric["unit"] == "days"
    assert metric["period"] == "week"


def test_empty_response_valid_structure(client, sample_project):
    """Empty responses should still have valid structure."""
    # Use sample_project which exists but may have no data
    response = client.get(f"/api/metrics/{sample_project.id}/throughput?weeks=4")
    
    if response.status_code == 200:
        data = response.json()
        assert data["status"] == "success"
        assert "data" in data
        metric = data["data"]
        assert metric["data"] == []  # Empty data array
        assert "stats" in metric
        assert "unit" in metric
        assert "period" in metric
    else:
        # If not 200, should still be a valid error response
        data = response.json()
        assert data["status"] == "error"
        assert "error" in data


def test_error_response_structure(client):
    """Error responses should follow ResponseEnvelope structure."""
    response = client.get("/api/metrics/999/throughput")
    
    if response.status_code != 200:
        # Should still be valid response (404, etc.)
        assert response.status_code in [404, 400, 500]
    else:
        # If 200, should have proper error structure in envelope
        data = response.json()
        # Valid response structure
        assert "status" in data
        assert "data" in data or "error" in data


def test_response_timestamp_format(client, sample_project):
    """Response timestamps should be ISO 8601 format."""
    response = client.get(f"/api/metrics/{sample_project.id}/throughput?weeks=4")
    assert response.status_code == 200
    
    data = response.json()
    timestamp = data["timestamp"]
    
    # Should be ISO 8601 with Z suffix
    assert "T" in timestamp
    assert timestamp.endswith("Z") or "+" in timestamp
    
    # Should be parseable as datetime
    try:
        if timestamp.endswith("Z"):
            datetime.fromisoformat(timestamp[:-1] + "+00:00")
        else:
            datetime.fromisoformat(timestamp)
    except ValueError:
        pytest.fail(f"Timestamp {timestamp} is not valid ISO 8601")


def test_metric_data_structure(client, sample_project):
    """Metric data points should follow MetricDataPoint structure."""
    response = client.get(f"/api/metrics/{sample_project.id}/throughput?weeks=4")
    assert response.status_code == 200
    
    data = response.json()
    metric = data["data"]
    
    if metric["data"]:  # If there's data
        point = metric["data"][0]
        assert "date" in point
        assert "value" in point
        # by_type is optional


def test_response_envelope_json_serializable(client, sample_project):
    """Response should be JSON serializable."""
    response = client.get(f"/api/metrics/{sample_project.id}/throughput?weeks=4")
    assert response.status_code == 200
    
    # Should not raise
    json.loads(response.text)
