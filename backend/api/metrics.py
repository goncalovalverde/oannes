from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Any, Dict, Literal
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np
import io
import csv
import logging
from database import get_db
from models.project import Project
from models.sync_job import CachedItem
from models.api_response import ResponseEnvelope, MetricResponse, MetricStats, MetricDataPoint, MetricsSummary
from calculator.flow import (
    cycle_time_by_interval as calc_cycle_time_by_interval,
    trim_leading_empty_buckets,
)
from services.metrics_service import MetricsService, ProjectNotFound as ServiceProjectNotFound

logger = logging.getLogger(__name__)

router = APIRouter()

_now = lambda: datetime.now(timezone.utc).replace(tzinfo=None)  # noqa: E731

logger = logging.getLogger(__name__)

router = APIRouter()

_now = lambda: datetime.now(timezone.utc).replace(tzinfo=None)  # noqa: E731


class MonteCarloRequest(BaseModel):
    project_id: int
    backlog_size: Optional[int] = None
    target_weeks: Optional[int] = None
    simulations: int = 10000
    weeks_history: int = 12


@router.get("/{project_id}/item-types")
def get_item_types(project_id: int, db: Session = Depends(get_db)):
    items = db.query(CachedItem.item_type).filter(CachedItem.project_id == project_id).distinct().all()
    return {"item_types": [i[0] for i in items if i[0]]}

@router.get("/{project_id}/throughput", response_model=ResponseEnvelope[MetricResponse])
def get_throughput(
    project_id: int,
    weeks: int = Query(520, ge=1, le=520, description="Time window in weeks (1-520)"),
    item_type: str = Query("all"),
    granularity: Literal["day", "week", "biweek", "month"] = Query("week"),
    db: Session = Depends(get_db)
):
    """Calculate throughput (items completed per period)."""
    try:
        service = MetricsService(db)
        response = service.throughput(project_id, weeks, item_type, granularity)
        return ResponseEnvelope(status="success", data=response)
    except ServiceProjectNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Throughput calculation failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{project_id}/cycle-time", response_model=ResponseEnvelope[MetricResponse])
def get_cycle_time(
    project_id: int,
    weeks: int = Query(520, ge=1, le=520, description="Time window in weeks (1-520)"),
    item_type: str = Query("all"),
    db: Session = Depends(get_db)
):
    """Calculate cycle time (median days from start to completion)."""
    try:
        service = MetricsService(db)
        response = service.cycle_time(project_id, weeks, item_type, granularity="week")
        return ResponseEnvelope(status="success", data=response)
    except ServiceProjectNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Cycle time calculation failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{project_id}/cycle-time-interval", response_model=ResponseEnvelope[MetricResponse])
def get_cycle_time_interval(
    project_id: int,
    weeks: int = Query(12),
    item_type: str = Query("all"),
    granularity: Literal["day", "week", "biweek", "month"] = Query("week"),
    db: Session = Depends(get_db)
):
    service = MetricsService(db)
    try:
        project = service._get_project(project_id)
    except ServiceProjectNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))

    df = service.get_items_df(project_id, weeks, item_type)
    if df.empty or "cycle_time_days" not in df.columns:
        return ResponseEnvelope(
            status="success",
            data=MetricResponse(
                data=[],
                stats=MetricStats(avg=0),
                unit="days",
                period=granularity
            )
        )

    steps = sorted(project.workflow_steps, key=lambda s: s.position)
    done_steps = [s for s in steps if s.stage == "done"]
    if not done_steps:
        return ResponseEnvelope(
            status="success",
            data=MetricResponse(
                data=[],
                stats=MetricStats(avg=0),
                unit="days",
                period=granularity
            )
        )

    done_col = done_steps[-1].display_name
    if done_col not in df.columns:
        return ResponseEnvelope(
            status="success",
            data=MetricResponse(
                data=[],
                stats=MetricStats(avg=0),
                unit="days",
                period=granularity
            )
        )

    ct_df = calc_cycle_time_by_interval(df, done_col=done_col, weeks=weeks, granularity=granularity)
    ct_df = trim_leading_empty_buckets(ct_df)
    if ct_df.empty:
        return ResponseEnvelope(
            status="success",
            data=MetricResponse(
                data=[],
                stats=MetricStats(avg=0),
                unit="days",
                period=granularity
            )
        )

    result = []
    values = []
    for idx, row in ct_df.iterrows():
        avg_ct = row.get("avg_cycle_time")
        if pd.notna(avg_ct):
            result.append(MetricDataPoint(
                date=idx.strftime("%Y-%m-%d"),
                value=float(round(avg_ct, 2))
            ))
            values.append(float(round(avg_ct, 2)))

    avg_value = float(np.mean(values)) if values else 0
    return ResponseEnvelope(
        status="success",
        data=MetricResponse(
            data=result,
            stats=MetricStats(avg=round(avg_value, 2)),
            unit="days",
            period=granularity
        )
    )

@router.get("/{project_id}/lead-time", response_model=ResponseEnvelope[MetricResponse])
def get_lead_time(
    project_id: int,
    weeks: int = Query(520, ge=1, le=520, description="Time window in weeks (1-520)"),
    item_type: str = Query("all"),
    db: Session = Depends(get_db)
):
    """Calculate lead time (created_at to done status)."""
    try:
        service = MetricsService(db)
        response = service.lead_time(project_id, weeks, item_type)
        return ResponseEnvelope(status="success", data=response)
    except ServiceProjectNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Lead time calculation failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{project_id}/wip", response_model=ResponseEnvelope[MetricResponse])
def get_wip(
    project_id: int,
    weeks: int = Query(520, ge=1, le=520, description="Time window in weeks (1-520)"),
    item_type: str = Query("all"),
    db: Session = Depends(get_db)
):
    """Calculate Work In Progress (items currently in flight)."""
    try:
        service = MetricsService(db)
        response = service.wip(project_id, weeks, item_type, granularity="week")
        return ResponseEnvelope(status="success", data=response)
    except ServiceProjectNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"WIP calculation failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{project_id}/cfd", response_model=ResponseEnvelope[MetricResponse])
def get_cfd(
    project_id: int,
    weeks: int = Query(520, ge=1, le=520, description="Time window in weeks (1-520)"),
    item_type: str = Query("all"),
    db: Session = Depends(get_db)
):
    """Calculate cumulative flow diagram data."""
    try:
        service = MetricsService(db)
        response = service.cfd(project_id, weeks, item_type)
        return ResponseEnvelope(status="success", data=response)
    except ServiceProjectNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"CFD calculation failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{project_id}/aging-wip", response_model=ResponseEnvelope[MetricResponse])
def get_aging_wip(
    project_id: int,
    weeks: int = Query(520, ge=1, le=520, description="Time window in weeks (1-520)"),
    item_type: str = Query("all"),
    db: Session = Depends(get_db)
):
    """Calculate age of work in progress items (loads weeks*4 history)."""
    try:
        service = MetricsService(db)
        response = service.aging_wip(project_id, weeks, item_type)
        return ResponseEnvelope(status="success", data=response)
    except ServiceProjectNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Aging WIP calculation failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{project_id}/flow-efficiency", response_model=ResponseEnvelope[MetricResponse])
@router.get("/{project_id}/flow-efficiency", response_model=ResponseEnvelope[MetricResponse])
def get_flow_efficiency(
    project_id: int,
    weeks: int = Query(520, ge=1, le=520, description="Time window in weeks (1-520)"),
    item_type: str = Query("all"),
    db: Session = Depends(get_db)
):
    """Calculate flow efficiency (active time / total time)."""
    try:
        service = MetricsService(db)
        response = service.flow_efficiency(project_id, weeks, item_type)
        return ResponseEnvelope(status="success", data=response)
    except ServiceProjectNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Flow efficiency calculation failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{project_id}/net-flow", response_model=ResponseEnvelope[MetricResponse])
def get_net_flow(
    project_id: int,
    weeks: int = Query(520, ge=1, le=520, description="Time window in weeks (1-520)"),
    item_type: str = Query("all"),
    granularity: Literal["day", "week", "biweek", "month"] = Query("week"),
    db: Session = Depends(get_db),
):
    """Calculate net flow (items completed - items added)."""
    try:
        service = MetricsService(db)
        response = service.net_flow(project_id, weeks, item_type, granularity)
        return ResponseEnvelope(status="success", data=response)
    except ServiceProjectNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Net flow calculation failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{project_id}/quality-rate", response_model=ResponseEnvelope[MetricResponse])
def get_quality_rate(
    project_id: int,
    weeks: int = Query(520, ge=1, le=520, description="Time window in weeks (1-520)"),
    item_type: str = Query("all", description="Filter by item type"),
    granularity: Literal["day", "week", "biweek", "month"] = Query("week"),
    db: Session = Depends(get_db),
):
    """Calculate quality rate (% of non-bug items completed).
    
    Returns percentage of completed items that are NOT bugs/defects, bucketed by time period.
    """
    try:
        service = MetricsService(db)
        response = service.quality_rate(project_id, weeks, item_type, granularity)
        return ResponseEnvelope(status="success", data=response)
    except ServiceProjectNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Quality metrics calculation failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{project_id}/summary", response_model=MetricsSummary)
def get_summary(
    project_id: int,
    weeks: int = Query(12),
    item_type: str = Query("all"),
    db: Session = Depends(get_db)
):
    """Return a dashboard summary — delegates entirely to MetricsService.summary()."""
    try:
        return MetricsService(db).summary(project_id, weeks, item_type)
    except ServiceProjectNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Summary calculation failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{project_id}/raw-data")
def get_raw_data(
    project_id: int,
    weeks: int = Query(52),
    item_type: str = Query("all"),
    db: Session = Depends(get_db)
):
    service = MetricsService(db)
    try:
        project = service._get_project(project_id)
    except ServiceProjectNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))

    df = service.get_items_df(project_id, weeks, item_type)
    if df.empty:
        return {"data": [], "columns": []}

    steps = sorted(project.workflow_steps, key=lambda s: s.position)
    step_cols = [s.display_name for s in steps if s.display_name in df.columns]

    base_cols = ["item_key", "item_type", "creator", "created_at", "cycle_time_days", "lead_time_days"]
    display_cols = [c for c in base_cols if c in df.columns] + step_cols

    result = []
    for _, row in df[display_cols].iterrows():
        rec = {}
        for col in display_cols:
            val = row.get(col)
            if pd.isna(val) if not isinstance(val, (str, dict, list)) else False:
                rec[col] = None
            elif hasattr(val, 'strftime'):
                rec[col] = val.strftime("%Y-%m-%d")
            else:
                rec[col] = val
        
        # Include status_transitions from the DataFrame
        transitions = df.loc[_, "status_transitions"] if "status_transitions" in df.columns else None
        if transitions:
            rec["status_transitions"] = transitions
        else:
            rec["status_transitions"] = []
        
        result.append(rec)

    return {"data": result, "columns": display_cols}

@router.get("/{project_id}/export-csv")
def export_csv(
    project_id: int,
    weeks: int = Query(52),
    item_type: str = Query("all"),
    db: Session = Depends(get_db)
):
    """Export raw data as CSV file."""
    service = MetricsService(db)
    try:
        project = service._get_project(project_id)
    except ServiceProjectNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))

    df = service.get_items_df(project_id, weeks, item_type)
    if df.empty:
        # Return empty CSV with headers
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=export.csv"}
        )

    steps = sorted(project.workflow_steps, key=lambda s: s.position)
    step_cols = [s.display_name for s in steps if s.display_name in df.columns]

    base_cols = ["item_key", "item_type", "creator", "created_at", "cycle_time_days", "lead_time_days"]
    display_cols = [c for c in base_cols if c in df.columns] + step_cols

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=display_cols)
    writer.writeheader()
    
    for _, row in df[display_cols].iterrows():
        rec = {}
        for col in display_cols:
            val = row.get(col)
            if pd.isna(val) if not isinstance(val, (str, dict, list)) else False:
                rec[col] = ""
            elif hasattr(val, 'strftime'):
                rec[col] = val.strftime("%Y-%m-%d")
            else:
                rec[col] = str(val) if val is not None else ""
        writer.writerow(rec)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=metrics_export.csv"}
    )

@router.get("/{project_id}/available-statuses")
def get_available_statuses(
    project_id: int,
    db: Session = Depends(get_db),
):
    """Return all distinct raw status names found in stored status_transitions.

    Used to help users build workflow configurations from real Jira status data.
    Items with NULL status_transitions (pre-feature sync) are skipped.
    """
    items = db.query(CachedItem).filter(CachedItem.project_id == project_id).all()
    if not items:
        raise HTTPException(status_code=404, detail="Project not found or no data synced")

    statuses: set[str] = set()
    for item in items:
        # Use the transitions relationship instead of status_transitions attribute
        for transition in (item.transitions or []):
            statuses.add(transition.to_status)

    return {"statuses": sorted(statuses)}


@router.post("/monte-carlo")
def run_monte_carlo(data: MonteCarloRequest, db: Session = Depends(get_db)):
    from calculator.monte_carlo import simulate_when_done, simulate_how_many

    service = MetricsService(db)
    try:
        tp = service.throughput(data.project_id, data.weeks_history, "all", granularity="week")
        throughput_series = [p.value for p in tp.data if p.value > 0]
    except ServiceProjectNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not throughput_series:
        raise HTTPException(status_code=400, detail="Insufficient throughput data for simulation")

    if data.backlog_size is not None:
        result = simulate_when_done(throughput_series, data.backlog_size, data.simulations)
        return {"mode": "when_done", "simulations": data.simulations, **result}
    elif data.target_weeks is not None:
        result = simulate_how_many(throughput_series, data.target_weeks, data.simulations)
        return {"mode": "how_many", "simulations": data.simulations, **result}
    else:
        raise HTTPException(status_code=400, detail="Either backlog_size or target_weeks required")
