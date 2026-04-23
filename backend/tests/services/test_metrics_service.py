"""Tests for MetricsService.

These tests verify business logic independently of HTTP layer.
Service layer can be tested without FastAPI or HTTP concerns.
"""
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from services.metrics_service import MetricsService, ProjectNotFound
from models.api_response import MetricResponse


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TestMetricsService:
    """Unit tests for MetricsService business logic."""
    
    def test_quality_rate_returns_metric_response(self, db, sample_project):
        """Service should return MetricResponse with correct structure."""
        service = MetricsService(db)
        response = service.quality_rate(
            project_id=sample_project.id,
            weeks=520,
            item_type="all",
            granularity="week"
        )
        
        assert isinstance(response, MetricResponse)
        assert hasattr(response, "data")
        assert hasattr(response, "stats")
        assert hasattr(response, "unit")
        assert response.unit == "%"
    
    def test_quality_rate_project_not_found(self, db):
        """Service should raise ProjectNotFound for missing project."""
        service = MetricsService(db)
        
        with pytest.raises(ProjectNotFound):
            service.quality_rate(
                project_id=999,
                weeks=520,
                item_type="all",
                granularity="week"
            )
    
    def test_quality_rate_empty_project(self, db, sample_project):
        """Service should return empty data for project with no items."""
        service = MetricsService(db)
        response = service.quality_rate(
            project_id=sample_project.id,
            weeks=520,
            item_type="all"
        )
        
        assert response.data == []
        assert response.stats.avg == 0
    
    def test_throughput_returns_metric_response(self, db, sample_project):
        """Service should return MetricResponse with throughput data."""
        service = MetricsService(db)
        response = service.throughput(
            project_id=sample_project.id,
            weeks=520,
            item_type="all",
            granularity="week"
        )
        
        assert isinstance(response, MetricResponse)
        assert response.unit == "items"
    
    def test_cycle_time_returns_metric_response(self, db, sample_project):
        """Service should return MetricResponse with cycle time data."""
        service = MetricsService(db)
        response = service.cycle_time(
            project_id=sample_project.id,
            weeks=520,
            item_type="all"
        )
        
        assert isinstance(response, MetricResponse)
        assert response.unit == "days"
    
    def test_wip_returns_metric_response(self, db, sample_project):
        """Service should return MetricResponse with WIP data."""
        service = MetricsService(db)
        response = service.wip(
            project_id=sample_project.id,
            weeks=520,
            item_type="all"
        )
        
        assert isinstance(response, MetricResponse)
        assert response.unit == "items"
    
    def test_lead_time_returns_metric_response(self, db, sample_project):
        """Service should return MetricResponse with lead time percentiles."""
        service = MetricsService(db)
        response = service.lead_time(
            project_id=sample_project.id,
            weeks=520,
            item_type="all"
        )
        
        assert isinstance(response, MetricResponse)
        assert response.unit == "days"
        assert response.period == "total"
        # Should have percentile stats
        assert hasattr(response.stats, "p50")
        assert hasattr(response.stats, "p95")
    
    def test_cfd_returns_metric_response(self, db, sample_project):
        """Service should return MetricResponse with CFD data."""
        service = MetricsService(db)
        response = service.cfd(
            project_id=sample_project.id,
            weeks=520,
            item_type="all"
        )
        
        assert isinstance(response, MetricResponse)
        assert response.unit == "items"
        assert response.period == "daily"
    
    def test_aging_wip_returns_metric_response(self, db, sample_project):
        """Service should return MetricResponse with aging WIP data."""
        service = MetricsService(db)
        response = service.aging_wip(
            project_id=sample_project.id,
            weeks=520,
            item_type="all"
        )
        
        assert isinstance(response, MetricResponse)
        assert response.unit == "days"
        assert response.period == "total"
    
    def test_flow_efficiency_returns_percentage(self, db, sample_project):
        """Service should return MetricResponse with flow efficiency (0-100%)."""
        service = MetricsService(db)
        response = service.flow_efficiency(
            project_id=sample_project.id,
            weeks=520,
            item_type="all"
        )
        
        assert isinstance(response, MetricResponse)
        assert response.unit == "%"
    
    def test_net_flow_returns_metric_response(self, db, sample_project):
        """Service should return MetricResponse with net flow data."""
        service = MetricsService(db)
        response = service.net_flow(
            project_id=sample_project.id,
            weeks=520,
            item_type="all"
        )
        
        assert isinstance(response, MetricResponse)
        assert response.unit == "items"
    
    def test_quality_rate_with_item_type_filter(self, db, sample_project):
        """Service should filter by item type."""
        service = MetricsService(db)
        
        all_response = service.quality_rate(
            project_id=sample_project.id,
            weeks=520,
            item_type="all"
        )
        
        bug_response = service.quality_rate(
            project_id=sample_project.id,
            weeks=520,
            item_type="bug"
        )
        
        # Both should return valid MetricResponse
        assert isinstance(all_response, MetricResponse)
        assert isinstance(bug_response, MetricResponse)
    
    def test_quality_rate_stats_calculated(self, db, sample_project):
        """Service should calculate average quality stats."""
        service = MetricsService(db)
        response = service.quality_rate(
            project_id=sample_project.id,
            weeks=520,
            item_type="all"
        )
        
        # Stats should always have avg field
        assert hasattr(response.stats, "avg")
        assert response.stats.avg >= 0
    
    def test_service_isolation_no_http(self, db, sample_project):
        """Service should work without any HTTP context.
        
        This test verifies that the service layer can be reused outside
        the HTTP/FastAPI layer, in CLI commands or background jobs.
        """
        service = MetricsService(db)
        
        # Should work fine without any HTTP request object
        quality = service.quality_rate(
            project_id=sample_project.id,
            weeks=520,
            item_type="all"
        )
        throughput = service.throughput(
            project_id=sample_project.id,
            weeks=520,
            item_type="all"
        )
        cycle = service.cycle_time(
            project_id=sample_project.id,
            weeks=520,
            item_type="all"
        )
        
        # All should return valid responses
        assert isinstance(quality, MetricResponse)
        assert isinstance(throughput, MetricResponse)
        assert isinstance(cycle, MetricResponse)
