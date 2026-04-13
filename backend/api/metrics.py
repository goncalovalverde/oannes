from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Any, Dict
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np
from database import get_db
from models.project import Project
from models.sync_job import CachedItem
from calculator.flow import (
    throughput as calc_throughput,
    cycle_time_stats,
    lead_time_stats,
    cfd as calc_cfd,
    wip_over_time,
    flow_efficiency as calc_flow_efficiency,
    net_flow as calc_net_flow,
)

router = APIRouter()

_now = lambda: datetime.now(timezone.utc).replace(tzinfo=None)  # noqa: E731

def get_items_df(project_id: int, weeks: int, item_type: str, db: Session) -> pd.DataFrame:
    """Load cached items into a DataFrame, filtered by date and type."""
    items = db.query(CachedItem).filter(CachedItem.project_id == project_id).all()
    if not items:
        return pd.DataFrame()

    records = []
    for item in items:
        record = {
            "item_key": item.item_key,
            "item_type": item.item_type,
            "creator": item.creator,
            "created_at": item.created_at,
            "cycle_time_days": item.cycle_time_days,
            "lead_time_days": item.lead_time_days,
        }
        if item.workflow_timestamps:
            record.update(item.workflow_timestamps)
        records.append(record)

    df = pd.DataFrame(records)
    if df.empty:
        return df

    date_cols = [c for c in df.columns if c not in {"item_key", "item_type", "creator", "cycle_time_days", "lead_time_days"}]
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

@router.get("/{project_id}/throughput")
def get_throughput(
    project_id: int,
    weeks: int = Query(12),
    item_type: str = Query("all"),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    df = get_items_df(project_id, weeks, item_type, db)
    if df.empty:
        return {"data": [], "avg": 0, "trend_pct": 0}

    steps = sorted(project.workflow_steps, key=lambda s: s.position)
    done_steps = [s for s in steps if s.stage == "done"]
    if not done_steps:
        return {"data": [], "avg": 0, "trend_pct": 0}

    done_col = done_steps[-1].display_name
    if done_col not in df.columns:
        return {"data": [], "avg": 0, "trend_pct": 0}

    tp_df = calc_throughput(df, done_col=done_col, weeks=weeks)
    if tp_df.empty:
        return {"data": [], "avg": 0, "trend_pct": 0}

    result = []
    totals = []
    for idx, row in tp_df.iterrows():
        total = int(row.get("Total", 0))
        by_type = {col: int(row[col]) for col in tp_df.columns if col != "Total"}
        totals.append(total)
        result.append({"week": idx.strftime("%Y-%m-%d"), "total": total, "by_type": by_type})

    avg = float(np.mean(totals)) if totals else 0
    half = len(totals) // 2
    if half > 0 and np.mean(totals[:half]) > 0:
        trend_pct = float((np.mean(totals[half:]) - np.mean(totals[:half])) / np.mean(totals[:half]) * 100)
    else:
        trend_pct = 0.0

    return {"data": result, "avg": round(avg, 1), "trend_pct": round(trend_pct, 1)}

@router.get("/{project_id}/cycle-time")
def get_cycle_time(
    project_id: int,
    weeks: int = Query(12),
    item_type: str = Query("all"),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    df = get_items_df(project_id, weeks, item_type, db)
    if df.empty or "cycle_time_days" not in df.columns:
        return {"data": [], "percentiles": {"p50": None, "p85": None, "p95": None}}

    steps = sorted(project.workflow_steps, key=lambda s: s.position)
    done_steps = [s for s in steps if s.stage == "done"]
    done_col = done_steps[-1].display_name if done_steps else None

    valid = df[df["cycle_time_days"].notna()].copy()
    data = []
    for _, row in valid.iterrows():
        completed_at = row.get(done_col, row.get("created_at", None)) if done_col else row.get("created_at", None)
        data.append({
            "item_key": str(row["item_key"]),
            "item_type": str(row["item_type"]),
            "completed_at": completed_at.strftime("%Y-%m-%d") if pd.notna(completed_at) and completed_at is not None else "",
            "cycle_time_days": float(row["cycle_time_days"])
        })

    stats = cycle_time_stats(df)
    pct = {"p50": stats["p50"], "p85": stats["p85"], "p95": stats["p95"]}
    return {"data": data, "percentiles": pct}

@router.get("/{project_id}/lead-time")
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
        return {"data": [], "percentiles": {"p50": None, "p85": None, "p95": None}}

    steps = sorted(project.workflow_steps, key=lambda s: s.position)
    done_steps = [s for s in steps if s.stage == "done"]
    done_col = done_steps[-1].display_name if done_steps else None

    valid = df[df["lead_time_days"].notna()].copy()
    data = []
    for _, row in valid.iterrows():
        completed_at = row.get(done_col, row.get("created_at", None)) if done_col else row.get("created_at", None)
        data.append({
            "item_key": str(row["item_key"]),
            "item_type": str(row["item_type"]),
            "completed_at": completed_at.strftime("%Y-%m-%d") if pd.notna(completed_at) and completed_at is not None else "",
            "lead_time_days": float(row["lead_time_days"])
        })

    stats = lead_time_stats(df)
    pct = {"p50": stats["p50"], "p85": stats["p85"], "p95": stats["p95"]}
    return {"data": data, "percentiles": pct}

@router.get("/{project_id}/wip")
def get_wip(
    project_id: int,
    weeks: int = Query(12),
    item_type: str = Query("all"),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    df = get_items_df(project_id, weeks * 2, item_type, db)
    steps = sorted(project.workflow_steps, key=lambda s: s.position)

    if df.empty or not steps:
        return {"data": [], "current_wip": 0}

    steps_list = [{"display_name": s.display_name, "stage": s.stage, "position": s.position, "source_statuses": s.source_statuses or []} for s in steps]
    wip_df = wip_over_time(df, steps_list, weeks=weeks)
    result = []
    for _, row in wip_df.iterrows():
        result.append({"date": row["date"].strftime("%Y-%m-%d") if hasattr(row["date"], "strftime") else str(row["date"]), "stage": row["stage"], "count": int(row["count"])})

    current_wip = 0
    in_flight_steps = [s for s in steps if s.stage == "in_flight"]
    done_steps = [s for s in steps if s.stage == "done"]
    if in_flight_steps and done_steps:
        start_col = in_flight_steps[0].display_name
        done_col = done_steps[-1].display_name
        if start_col in df.columns and done_col in df.columns:
            started = df[df[start_col].notna()]
            not_done = started[started[done_col].isna()]
            current_wip = len(not_done)

    return {"data": result, "current_wip": current_wip}

@router.get("/{project_id}/cfd")
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
        return {"data": [], "stages": []}

    stage_names = [s.display_name for s in steps if s.display_name in df.columns]
    if not stage_names:
        return {"data": [], "stages": []}

    steps_list = [{"display_name": s.display_name, "stage": s.stage, "position": s.position, "source_statuses": s.source_statuses or []} for s in steps]
    cfd_df = calc_cfd(df, steps_list)
    result = []
    for idx, row in cfd_df.iterrows():
        r = {"date": idx.strftime("%Y-%m-%d")}
        for stage in stage_names:
            r[stage] = int(row.get(stage, 0))
        result.append(r)

    return {"data": result, "stages": stage_names}

@router.get("/{project_id}/aging-wip")
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
        return {"data": [], "p85_benchmark": None}

    in_flight_steps = [s for s in steps if s.stage == "in_flight"]
    done_steps = [s for s in steps if s.stage == "done"]

    if not in_flight_steps or not done_steps:
        return {"data": [], "p85_benchmark": None}

    start_step = in_flight_steps[0]
    done_col = done_steps[-1].display_name

    stats = cycle_time_stats(df)
    p85 = stats.get("p85")

    start_col = start_step.display_name
    if start_col not in df.columns:
        return {"data": [], "p85_benchmark": p85}

    in_progress = df[df[start_col].notna()]
    if done_col in df.columns:
        in_progress = in_progress[in_progress[done_col].isna()]

    now = pd.Timestamp(_now())
    result = []
    for _, row in in_progress.iterrows():
        age = (now - row[start_col]).days if pd.notna(row[start_col]) else 0

        current_stage = start_step.display_name
        for step in reversed(steps):
            sc = step.display_name
            if sc in df.columns and pd.notna(row.get(sc)):
                current_stage = step.display_name
                break

        result.append({
            "item_key": str(row["item_key"]),
            "item_type": str(row["item_type"]),
            "stage": current_stage,
            "age_days": float(age),
            "is_over_85th": (p85 is not None and age > p85)
        })

    result.sort(key=lambda x: x["age_days"], reverse=True)
    return {"data": result, "p85_benchmark": p85}

@router.get("/{project_id}/flow-efficiency")
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
        return {"flow_efficiency": 0.0}

    steps_list = [{"display_name": s.display_name, "stage": s.stage, "position": s.position, "source_statuses": s.source_statuses or []} for s in steps]
    fe = calc_flow_efficiency(df, steps_list)
    return {"flow_efficiency": fe}


@router.get("/{project_id}/net-flow")
def get_net_flow(
    project_id: int,
    weeks: int = Query(12),
    item_type: str = Query("all"),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    df = get_items_df(project_id, weeks, item_type, db)
    if df.empty:
        return {"data": []}

    steps = sorted(project.workflow_steps, key=lambda s: s.position)
    if not steps:
        return {"data": []}

    start_col = next((s.display_name for s in steps if s.stage in ("start", "in_flight")), steps[0].display_name)
    done_col  = next((s.display_name for s in reversed(steps) if s.stage == "done"), steps[-1].display_name)

    result_df = calc_net_flow(df, start_col, done_col, weeks)
    if result_df.empty:
        return {"data": []}

    records = result_df.copy()
    records["week"] = records["week"].dt.strftime("%Y-%m-%d")
    return {"data": records.to_dict(orient="records")}


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
        result.append(rec)

    return {"data": result, "columns": display_cols}

@router.post("/monte-carlo")
def run_monte_carlo(data: MonteCarloRequest, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == data.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    from calculator.monte_carlo import simulate_when_done, simulate_how_many

    tp = get_throughput(data.project_id, data.weeks_history, "all", db)
    throughput_series = [p["total"] for p in tp.get("data", []) if p["total"] > 0]

    if not throughput_series:
        raise HTTPException(status_code=400, detail="Insufficient throughput data for simulation")

    if data.backlog_size is not None:
        result = simulate_when_done(throughput_series, data.backlog_size, data.simulations)
        return {"mode": "when_done", **result}
    elif data.target_weeks is not None:
        result = simulate_how_many(throughput_series, data.target_weeks, data.simulations)
        return {"mode": "how_many", **result}
    else:
        raise HTTPException(status_code=400, detail="Either backlog_size or target_weeks required")
