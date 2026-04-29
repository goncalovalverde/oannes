"""Helper functions for standardizing metrics API responses.

Converts current metric endpoint responses to ResponseEnvelope[MetricResponse] format.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
import numpy as np
from models.api_response import (
    ResponseEnvelope, MetricResponse, MetricDataPoint, MetricStats,
    create_success_response
)


def build_throughput_response(
    data: List[Dict[str, Any]],
    totals: List[float],
    granularity: str = "week"
) -> ResponseEnvelope[MetricResponse]:
    """Build standardized throughput response.
    
    Args:
        data: List of dicts with 'week', 'total', 'by_type' keys
        totals: List of total counts for trend calculation
        granularity: Period granularity (day, week, biweek, month)
        
    Returns:
        ResponseEnvelope with MetricResponse
    """
    avg = float(np.mean(totals)) if totals else 0
    half = len(totals) // 2
    if half > 0 and np.mean(totals[:half]) > 0:
        trend_pct = float((np.mean(totals[half:]) - np.mean(totals[:half])) / np.mean(totals[:half]) * 100)
    else:
        trend_pct = 0.0

    p50 = round(float(np.percentile(totals, 50)), 1) if totals else None
    p85 = round(float(np.percentile(totals, 85)), 1) if totals else None
    p95 = round(float(np.percentile(totals, 95)), 1) if totals else None
    
    metric_data = [
        MetricDataPoint(
            date=item["week"],
            value=item["total"],
            by_type=item.get("by_type", {})
        )
        for item in data
    ]
    
    response = MetricResponse(
        data=metric_data,
        stats=MetricStats(
            avg=round(avg, 1),
            trend_pct=round(trend_pct, 1),
            p50=p50,
            p85=p85,
            p95=p95
        ),
        unit="items",
        period=granularity
    )
    
    return create_success_response(response)


def build_cycle_time_response(
    data: List[Dict[str, Any]],
    percentiles: Dict[str, Optional[float]]
) -> ResponseEnvelope[MetricResponse]:
    """Build standardized cycle time response (item-level).
    
    Args:
        data: List of dicts with 'item_key', 'cycle_time_days', etc.
        percentiles: Dict with p50, p85, p95 percentiles
        
    Returns:
        ResponseEnvelope with MetricResponse
    """
    cycle_times = [item["cycle_time_days"] for item in data if "cycle_time_days" in item]
    
    metric_data = [
        MetricDataPoint(
            date=item.get("completed_at", ""),
            value=item["cycle_time_days"]
        )
        for item in data
    ]
    
    response = MetricResponse(
        data=metric_data,
        stats=MetricStats(
            avg=float(np.mean(cycle_times)) if cycle_times else 0,
            p50=percentiles.get("p50"),
            p85=percentiles.get("p85"),
            p95=percentiles.get("p95")
        ),
        unit="days",
        period="individual"
    )
    
    return create_success_response(response)


def build_cycle_time_interval_response(
    data: List[Dict[str, Any]],
    granularity: str = "week"
) -> ResponseEnvelope[MetricResponse]:
    """Build standardized cycle time interval response.
    
    Args:
        data: List of dicts with 'period', 'avg_cycle_time' keys
        granularity: Period granularity (day, week, biweek, month)
        
    Returns:
        ResponseEnvelope with MetricResponse
    """
    avgs = [item["avg_cycle_time"] for item in data if "avg_cycle_time" in item]
    
    metric_data = [
        MetricDataPoint(
            date=item["period"],
            value=item["avg_cycle_time"]
        )
        for item in data
    ]
    
    response = MetricResponse(
        data=metric_data,
        stats=MetricStats(
            avg=float(np.mean(avgs)) if avgs else 0
        ),
        unit="days",
        period=granularity
    )
    
    return create_success_response(response)


def build_lead_time_response(
    data: List[Dict[str, Any]],
    percentiles: Dict[str, Optional[float]]
) -> ResponseEnvelope[MetricResponse]:
    """Build standardized lead time response (item-level).
    
    Args:
        data: List of dicts with 'item_key', 'lead_time_days', etc.
        percentiles: Dict with p50, p85, p95 percentiles
        
    Returns:
        ResponseEnvelope with MetricResponse
    """
    lead_times = [item["lead_time_days"] for item in data if "lead_time_days" in item]
    
    metric_data = [
        MetricDataPoint(
            date=item.get("created_at", ""),
            value=item["lead_time_days"]
        )
        for item in data
    ]
    
    response = MetricResponse(
        data=metric_data,
        stats=MetricStats(
            avg=float(np.mean(lead_times)) if lead_times else 0,
            p50=percentiles.get("p50"),
            p85=percentiles.get("p85"),
            p95=percentiles.get("p95")
        ),
        unit="days",
        period="individual"
    )
    
    return create_success_response(response)


def build_wip_response(
    data: List[Dict[str, Any]]
) -> ResponseEnvelope[MetricResponse]:
    """Build standardized WIP response.
    
    Args:
        data: List of dicts with 'date', 'count', 'by_type' keys
        
    Returns:
        ResponseEnvelope with MetricResponse
    """
    counts = [item.get("count", 0) for item in data]
    
    metric_data = [
        MetricDataPoint(
            date=item["date"],
            value=item.get("count", 0),
            by_type=item.get("by_type", {})
        )
        for item in data
    ]
    
    response = MetricResponse(
        data=metric_data,
        stats=MetricStats(
            avg=float(np.mean(counts)) if counts else 0,
            min=int(min(counts)) if counts else 0,
            max=int(max(counts)) if counts else 0
        ),
        unit="items",
        period="daily"
    )
    
    return create_success_response(response)


def build_cfd_response(
    data: List[Dict[str, Any]]
) -> ResponseEnvelope[MetricResponse]:
    """Build standardized CFD (Cumulative Flow Diagram) response.
    
    Args:
        data: List of dicts with 'date', 'status_name', 'cumulative_count' keys
        
    Returns:
        ResponseEnvelope with MetricResponse
    """
    metric_data = [
        MetricDataPoint(
            date=item["date"],
            value=item.get("cumulative_count", 0),
            by_type={"status": item.get("status_name", "unknown")}
        )
        for item in data
    ]
    
    response = MetricResponse(
        data=metric_data,
        stats=MetricStats(avg=0),  # CFD is cumulative, not average
        unit="items",
        period="daily"
    )
    
    return create_success_response(response)


def build_aging_wip_response(
    data: List[Dict[str, Any]]
) -> ResponseEnvelope[MetricResponse]:
    """Build standardized aging WIP response.
    
    Args:
        data: List of dicts with 'item_key', 'age_days', 'status' keys
        
    Returns:
        ResponseEnvelope with MetricResponse
    """
    ages = [item.get("age_days", 0) for item in data]
    
    metric_data = [
        MetricDataPoint(
            date=item.get("status", "unknown"),
            value=item.get("age_days", 0)
        )
        for item in data
    ]
    
    response = MetricResponse(
        data=metric_data,
        stats=MetricStats(
            avg=float(np.mean(ages)) if ages else 0,
            min=float(min(ages)) if ages else 0,
            max=float(max(ages)) if ages else 0
        ),
        unit="days",
        period="current"
    )
    
    return create_success_response(response)


def build_flow_efficiency_response(
    data: List[Dict[str, Any]]
) -> ResponseEnvelope[MetricResponse]:
    """Build standardized flow efficiency response.
    
    Args:
        data: List of dicts with 'date', 'efficiency_pct' keys
        
    Returns:
        ResponseEnvelope with MetricResponse
    """
    efficiencies = [item.get("efficiency_pct", 0) for item in data]
    
    metric_data = [
        MetricDataPoint(
            date=item["date"],
            value=item.get("efficiency_pct", 0)
        )
        for item in data
    ]
    
    response = MetricResponse(
        data=metric_data,
        stats=MetricStats(
            avg=float(np.mean(efficiencies)) if efficiencies else 0,
            min=float(min(efficiencies)) if efficiencies else 0,
            max=float(max(efficiencies)) if efficiencies else 0
        ),
        unit="%",
        period="weekly"
    )
    
    return create_success_response(response)


def build_net_flow_response(
    data: List[Dict[str, Any]]
) -> ResponseEnvelope[MetricResponse]:
    """Build standardized net flow response.
    
    Args:
        data: List of dicts with 'date', 'inflow', 'outflow', 'net' keys
        
    Returns:
        ResponseEnvelope with MetricResponse
    """
    metric_data = [
        MetricDataPoint(
            date=item["date"],
            value=item.get("net", 0),
            by_type={
                "inflow": item.get("inflow", 0),
                "outflow": item.get("outflow", 0)
            }
        )
        for item in data
    ]
    
    response = MetricResponse(
        data=metric_data,
        stats=MetricStats(avg=0),  # Net flow is directional
        unit="items",
        period="weekly"
    )
    
    return create_success_response(response)
