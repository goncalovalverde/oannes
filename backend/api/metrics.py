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
from models.api_response import ResponseEnvelope, MetricResponse, MetricStats, MetricDataPoint
from calculator.flow import (
    throughput as calc_throughput,
    cycle_time_by_interval as calc_cycle_time_by_interval,
    cycle_time_stats,
    lead_time_stats,
    cfd as calc_cfd,
    wip_over_time,
    flow_efficiency as calc_flow_efficiency,
    net_flow as calc_net_flow,
    quality_rate as calc_quality_rate,
    trim_leading_empty_buckets,
)
from services.metrics_service import MetricsService, ProjectNotFound as ServiceProjectNotFound

logger = logging.getLogger(__name__)

router = APIRouter()

_now = lambda: datetime.now(timezone.utc).replace(tzinfo=None)  # noqa: E731

def get_items_df(project_id: int, weeks: int, item_type: str, db: Session) -> pd.DataFrame:
    """Load cached items into a DataFrame, filtered by date and type."""
    items = db.query(CachedItem).filter(CachedItem.project_id == project_id).all()
    if not items:
        return pd.DataFrame()

    records = []
    for item in items:
        # Convert ItemTransition objects to list of dicts for compatibility with sync_service
        status_transitions = None
        if item.transitions:
            status_transitions = [
                {
                    "from_status": t.from_status,
                    "to_status": t.to_status,
                    "transitioned_at": t.transitioned_at,
                }
                for t in item.transitions
            ]
        
        record = {
            "item_key": item.item_key,
            "item_type": item.item_type,
            "creator": item.creator,
            "created_at": item.created_at,
            "cycle_time_days": item.cycle_time_days,
            "lead_time_days": item.lead_time_days,
            "status_transitions": status_transitions,
        }
        if item.workflow_timestamps:
            record.update(item.workflow_timestamps)
        records.append(record)

    df = pd.DataFrame(records)
    if df.empty:
        return df

    date_cols = [c for c in df.columns if c not in {"item_key", "item_type", "creator", "cycle_time_days", "lead_time_days", "status_transitions"}]
    for col in date_cols:
        try:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
            df[col] = df[col].dt.tz_localize(None)
        except Exception:
            pass

    if item_type and item_type != "all":
        df = df[df["item_type"] == item_type]

    if weeks and weeks > 0:
        cutoff = _now() - timedelta(weeks=weeks)
        if "created_at" in df.columns:
            df = df[df["created_at"] >= cutoff]

    return df

def percentiles(series: pd.Series) -> dict:
    clean = series.dropna()
    if clean.empty:
        return {"p50": None, "p85": None, "p95": None}
    return {
        "p50": float(np.percentile(clean, 50)),
        "p85": float(np.percentile(clean, 85)),
        "p95": float(np.percentile(clean, 95)),
    }

class MonteCarloRequest(BaseModel):
    project_id: int
    backlog_size: Optional[int] = None
    target_weeks: Optional[int] = None
    simulations: int = 10000
    weeks_history: int = 12

class MetricsSummary(BaseModel):
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
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    df = get_items_df(project_id, weeks, item_type, db)
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
    weeks: int = Query(12),
    item_type: str = Query("all"),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    df = get_items_df(project_id, weeks, item_type, db)
    if df.empty or "lead_time_days" not in df.columns:
        return ResponseEnvelope(
            status="success",
            data=MetricResponse(
                data=[],
                stats=MetricStats(avg=0, p50=None, p85=None, p95=None),
                unit="days",
                period="total"
            )
        )

    steps = sorted(project.workflow_steps, key=lambda s: s.position)
    done_steps = [s for s in steps if s.stage == "done"]
    done_col = done_steps[-1].display_name if done_steps else None

    valid = df[df["lead_time_days"].notna()].copy()
    data = []
    for _, row in valid.iterrows():
        completed_at = row.get(done_col, row.get("created_at", None)) if done_col else row.get("created_at", None)
        data.append(MetricDataPoint(
            date=completed_at.strftime("%Y-%m-%d") if pd.notna(completed_at) and completed_at is not None else "",
            value=float(row["lead_time_days"]),
            by_type={"item_key": str(row["item_key"]), "item_type": str(row["item_type"])}
        ))

    stats = lead_time_stats(df)
    return ResponseEnvelope(
        status="success",
        data=MetricResponse(
            data=data,
            stats=MetricStats(
                avg=stats.get("p50", 0) or 0,
                p50=stats.get("p50"),
                p85=stats.get("p85"),
                p95=stats.get("p95")
            ),
            unit="days",
            period="total"
        )
    )

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
    weeks: int = Query(12),
    item_type: str = Query("all"),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    df = get_items_df(project_id, weeks, item_type, db)
    steps = sorted(project.workflow_steps, key=lambda s: s.position)

    if df.empty or not steps:
        return ResponseEnvelope(
            status="success",
            data=MetricResponse(
                data=[],
                stats=MetricStats(avg=0),
                unit="items",
                period="daily"
            )
        )

    stage_names = [s.display_name for s in steps if s.display_name in df.columns]
    if not stage_names:
        return ResponseEnvelope(
            status="success",
            data=MetricResponse(
                data=[],
                stats=MetricStats(avg=0),
                unit="items",
                period="daily"
            )
        )

    steps_list = [{"display_name": s.display_name, "stage": s.stage, "position": s.position, "source_statuses": s.source_statuses or []} for s in steps]
    cfd_df = calc_cfd(df, steps_list)
    
    result = []
    for idx, row in cfd_df.iterrows():
        date_str = idx.strftime("%Y-%m-%d")
        for stage in stage_names:
            count = int(row.get(stage, 0))
            result.append(MetricDataPoint(
                date=date_str,
                value=float(count),
                by_type={"stage": stage}
            ))

    return ResponseEnvelope(
        status="success",
        data=MetricResponse(
            data=result,
            stats=MetricStats(avg=0),
            unit="items",
            period="daily"
        )
    )

@router.get("/{project_id}/aging-wip", response_model=ResponseEnvelope[MetricResponse])
def get_aging_wip(
    project_id: int,
    weeks: int = Query(12),
    item_type: str = Query("all"),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    df = get_items_df(project_id, weeks * 4, item_type, db)
    steps = sorted(project.workflow_steps, key=lambda s: s.position)

    if df.empty or not steps:
        return ResponseEnvelope(
            status="success",
            data=MetricResponse(
                data=[],
                stats=MetricStats(avg=0),
                unit="days",
                period="total"
            )
        )

    in_flight_steps = [s for s in steps if s.stage == "in_flight"]
    done_steps = [s for s in steps if s.stage == "done"]

    if not in_flight_steps or not done_steps:
        return ResponseEnvelope(
            status="success",
            data=MetricResponse(
                data=[],
                stats=MetricStats(avg=0),
                unit="days",
                period="total"
            )
        )

    start_step = in_flight_steps[0]
    done_col = done_steps[-1].display_name

    stats = cycle_time_stats(df)
    p85 = stats.get("p85")

    start_col = start_step.display_name
    if start_col not in df.columns:
        return ResponseEnvelope(
            status="success",
            data=MetricResponse(
                data=[],
                stats=MetricStats(avg=p85 or 0, p85=p85),
                unit="days",
                period="total"
            )
        )

    in_progress = df[df[start_col].notna()]
    if done_col in df.columns:
        in_progress = in_progress[in_progress[done_col].isna()]

    now = pd.Timestamp(_now())
    result = []
    ages = []
    for _, row in in_progress.iterrows():
        age = (now - row[start_col]).days if pd.notna(row[start_col]) else 0

        current_stage = start_step.display_name
        for step in reversed(steps):
            sc = step.display_name
            if sc in df.columns and pd.notna(row.get(sc)):
                current_stage = step.display_name
                break

        result.append(MetricDataPoint(
            date="",
            value=float(age),
            by_type={
                "item_key": str(row["item_key"]),
                "item_type": str(row["item_type"]),
                "stage": current_stage,
                "is_over_85th": p85 is not None and age > p85
            }
        ))
        ages.append(float(age))

    result.sort(key=lambda x: x.value, reverse=True)
    avg_age = float(np.mean(ages)) if ages else 0
    return ResponseEnvelope(
        status="success",
        data=MetricResponse(
            data=result,
            stats=MetricStats(avg=round(avg_age, 1), p85=p85),
            unit="days",
            period="total"
        )
    )

@router.get("/{project_id}/flow-efficiency", response_model=ResponseEnvelope[MetricResponse])
def get_flow_efficiency(
    project_id: int,
    weeks: int = Query(12),
    item_type: str = Query("all"),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    df = get_items_df(project_id, weeks, item_type, db)
    steps = sorted(project.workflow_steps, key=lambda s: s.position)

    if df.empty or not steps:
        return ResponseEnvelope(
            status="success",
            data=MetricResponse(
                data=[],
                stats=MetricStats(avg=0),
                unit="%",
                period="total"
            )
        )

    steps_list = [{"display_name": s.display_name, "stage": s.stage, "position": s.position, "source_statuses": s.source_statuses or []} for s in steps]
    fe = calc_flow_efficiency(df, steps_list)
    return ResponseEnvelope(
        status="success",
        data=MetricResponse(
            data=[MetricDataPoint(date="", value=float(fe))],
            stats=MetricStats(avg=float(fe)),
            unit="%",
            period="total"
        )
    )


@router.get("/{project_id}/net-flow", response_model=ResponseEnvelope[MetricResponse])
def get_net_flow(
    project_id: int,
    weeks: int = Query(12),
    item_type: str = Query("all"),
    granularity: Literal["day", "week", "biweek", "month"] = Query("week"),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    df = get_items_df(project_id, weeks, item_type, db)
    if df.empty:
        return ResponseEnvelope(
            status="success",
            data=MetricResponse(
                data=[],
                stats=MetricStats(avg=0),
                unit="items",
                period=granularity
            )
        )

    steps = sorted(project.workflow_steps, key=lambda s: s.position)
    if not steps:
        return ResponseEnvelope(
            status="success",
            data=MetricResponse(
                data=[],
                stats=MetricStats(avg=0),
                unit="items",
                period=granularity
            )
        )

    start_col = next((s.display_name for s in steps if s.stage in ("start", "in_flight")), steps[0].display_name)
    done_col  = next((s.display_name for s in reversed(steps) if s.stage == "done"), steps[-1].display_name)

    result_df = calc_net_flow(df, start_col, done_col, weeks, granularity=granularity)
    result_df = trim_leading_empty_buckets(result_df)
    if result_df.empty:
        return ResponseEnvelope(
            status="success",
            data=MetricResponse(
                data=[],
                stats=MetricStats(avg=0),
                unit="items",
                period=granularity
            )
        )

    records = result_df.copy()
    records["week"] = records["week"].dt.strftime("%Y-%m-%d")
    
    data = []
    net_values = []
    for _, row in records.iterrows():
        arrivals = int(row.get("arrivals", 0))
        completions = int(row.get("completions", 0))
        net = int(row.get("net", 0))
        data.append(MetricDataPoint(
            date=row["week"],
            value=float(net),
            by_type={
                "arrivals": arrivals,
                "completions": completions,
                "net": net
            }
        ))
        net_values.append(net)

    avg_value = float(np.mean(net_values)) if net_values else 0
    return ResponseEnvelope(
        status="success",
        data=MetricResponse(
            data=data,
            stats=MetricStats(avg=round(avg_value, 1)),
            unit="items",
            period=granularity
        )
    )


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
    """Return a dashboard summary using a *single* DB query.

    Previously this called 7 sub-endpoints, each issuing its own DB scan.
    Now we load CachedItems once (wide window to capture open/aging items),
    derive a narrow slice for time-bounded metrics, and call calculator
    functions directly on the DataFrames.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    steps = sorted(project.workflow_steps, key=lambda s: s.position)
    done_steps = [s for s in steps if s.stage == "done"]
    in_flight_steps = [s for s in steps if s.stage == "in_flight"]
    done_col = done_steps[-1].display_name if done_steps else None
    steps_list = [
        {"display_name": s.display_name, "stage": s.stage,
         "position": s.position, "source_statuses": s.source_statuses or []}
        for s in steps
    ]

    # One DB query — wide window covers all open/aging items (they may pre-date `weeks`)
    df_wide = get_items_df(project_id, weeks * 4, item_type, db)

    # Narrow slice for time-bounded metrics (throughput, CT, LT, flow efficiency)
    if not df_wide.empty and "created_at" in df_wide.columns:
        cutoff = pd.Timestamp(_now()) - pd.Timedelta(weeks=weeks)
        df = df_wide[df_wide["created_at"] >= cutoff].copy()
    else:
        df = df_wide

    # item_types — derived from the wide frame so we see all types, not just recent ones
    item_types: List[str] = (
        sorted(df_wide["item_type"].dropna().unique().tolist()) if not df_wide.empty else []
    )

    # --- Throughput (narrow window) ---
    throughput_avg, throughput_trend_pct = 0.0, 0.0
    if not df.empty and done_col and done_col in df.columns:
        tp_df = calc_throughput(df, done_col=done_col, weeks=weeks)
        if not tp_df.empty:
            totals = [int(r.get("Total", 0)) for _, r in tp_df.iterrows()]
            throughput_avg = float(np.mean(totals)) if totals else 0.0
            half = len(totals) // 2
            if half > 0 and np.mean(totals[:half]) > 0:
                throughput_trend_pct = float(
                    (np.mean(totals[half:]) - np.mean(totals[:half]))
                    / np.mean(totals[:half]) * 100
                )

    # --- Cycle time & lead time percentiles (narrow window) ---
    ct_stats = cycle_time_stats(df) if not df.empty else {}
    lt_stats = lead_time_stats(df) if not df.empty else {}

    # --- Current WIP — open in-flight items (wide frame: captures old starters) ---
    current_wip = 0
    if not df_wide.empty and in_flight_steps and done_col:
        start_col = in_flight_steps[0].display_name
        if start_col in df_wide.columns and done_col in df_wide.columns:
            current_wip = int(
                (df_wide[start_col].notna() & df_wide[done_col].isna()).sum()
            )

    # --- Flow efficiency (narrow window) ---
    fe = calc_flow_efficiency(df, steps_list) if (not df.empty and steps_list) else 0.0

    # --- Aging WIP alerts (wide frame: open items over p85 CT threshold) ---
    aging_wip_alerts = 0
    p85 = ct_stats.get("p85")
    if not df_wide.empty and in_flight_steps and done_col and p85 is not None:
        start_col = in_flight_steps[0].display_name
        if start_col in df_wide.columns and done_col in df_wide.columns:
            open_items = df_wide[df_wide[start_col].notna() & df_wide[done_col].isna()]
            if not open_items.empty:
                now_ts = pd.Timestamp(_now())
                ages = open_items[start_col].apply(
                    lambda t: (now_ts - t).days if pd.notna(t) else 0
                ).astype("int64")
                aging_wip_alerts = int((ages > p85).sum())

    return MetricsSummary(
        throughput_avg=round(throughput_avg, 1),
        throughput_trend_pct=round(throughput_trend_pct, 1),
        cycle_time_avg=ct_stats.get("mean"),
        cycle_time_50th=ct_stats.get("p50"),
        cycle_time_85th=ct_stats.get("p85"),
        cycle_time_95th=ct_stats.get("p95"),
        lead_time_85th=lt_stats.get("p85"),
        current_wip=current_wip,
        flow_efficiency=round(fe, 4),
        aging_wip_alerts=aging_wip_alerts,
        item_types=item_types,
    )

@router.get("/{project_id}/raw-data")
def get_raw_data(
    project_id: int,
    weeks: int = Query(52),
    item_type: str = Query("all"),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    df = get_items_df(project_id, weeks, item_type, db)
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
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    df = get_items_df(project_id, weeks, item_type, db)
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
    project = db.query(Project).filter(Project.id == data.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    from calculator.monte_carlo import simulate_when_done, simulate_how_many

    tp = get_throughput(data.project_id, data.weeks_history, "all", granularity="week", db=db)
    throughput_series = [p["total"] for p in tp.get("data", []) if p["total"] > 0]

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
