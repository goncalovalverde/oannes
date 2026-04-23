"""MetricsService: Calculate and format metrics for projects.

Extracted from api/metrics.py to satisfy SRP: the API layer only handles HTTP,
this service handles all business logic (querying, calculating, formatting).

This enables:
- Testing metrics calculations without HTTP framework
- Reusing metrics in CLI commands, background jobs, etc.
- Changing API response formats without touching business logic
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd
import numpy as np
from sqlalchemy.orm import Session

from models.project import Project
from models.sync_job import CachedItem
from models.api_response import MetricResponse, MetricStats, MetricDataPoint
from models.item_transition import ItemTransition
from calculator.flow import (
    quality_rate as calc_quality_rate,
    throughput as calc_throughput,
    cycle_time_by_interval as calc_cycle_time_by_interval,
    cycle_time_stats,
    lead_time_stats,
    cfd as calc_cfd,
    wip_over_time,
    flow_efficiency as calc_flow_efficiency,
    net_flow as calc_net_flow,
    trim_leading_empty_buckets,
)

logger = logging.getLogger(__name__)


class ProjectNotFound(Exception):
    """Raised when project doesn't exist."""
    pass


def _utcnow() -> datetime:
    """Return current time in UTC without timezone info."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MetricsService:
    """Calculate and format metrics for a project.
    
    Public methods should return MetricResponse objects or raise custom exceptions.
    All database queries handled internally.
    """
    
    def __init__(self, db: Session) -> None:
        """Initialize with database session."""
        self._db = db
    
    # ------------------------------------------------------------------
    # Quality Metrics
    # ------------------------------------------------------------------
    
    def quality_rate(self, project_id: int, weeks: int, item_type: str = "all",
                     granularity: str = "week") -> MetricResponse:
        """Calculate quality rate (% of non-bug items completed).
        
        Args:
            project_id: Project ID
            weeks: Time window in weeks (use calculation to determine if needed)
            item_type: Filter by item type ('all' for no filter)
            granularity: Time bucket ('day', 'week', 'biweek', 'month')
        
        Returns:
            MetricResponse with quality data
        
        Raises:
            ProjectNotFound: If project doesn't exist
        """
        project = self._get_project(project_id)
        df = self._get_items_df(project_id, weeks, item_type)
        
        if df.empty:
            return MetricResponse(data=[], stats=MetricStats(avg=0), unit="%", period=granularity)
        
        # Find done column for quality calculation
        done_col = self._get_done_column(project)
        if not done_col:
            return MetricResponse(data=[], stats=MetricStats(avg=0), unit="%", period=granularity)
        
        # Calculate quality rate over time
        result_df = calc_quality_rate(df, done_col, weeks, granularity=granularity)
        result_df = trim_leading_empty_buckets(result_df)
        
        if result_df.empty:
            return MetricResponse(data=[], stats=MetricStats(avg=0), unit="%", period=granularity)
        
        # Format as MetricDataPoint with bugs breakdown
        data_points = self._quality_df_to_metric_points(result_df)
        avg_quality = self._calculate_average([p.value for p in data_points]) if data_points else 0
        
        return MetricResponse(
            data=data_points,
            stats=MetricStats(avg=round(avg_quality, 1)),
            unit="%",
            period=granularity
        )
    
    # ------------------------------------------------------------------
    # Throughput Metrics
    # ------------------------------------------------------------------
    
    def throughput(self, project_id: int, weeks: int, item_type: str = "all",
                   granularity: str = "week") -> MetricResponse:
        """Calculate throughput (items completed per period).
        
        Args:
            project_id: Project ID
            weeks: Time window in weeks
            item_type: Filter by item type ('all' for no filter)
            granularity: Time bucket ('day', 'week', 'biweek', 'month')
        
        Returns:
            MetricResponse with throughput data
        
        Raises:
            ProjectNotFound: If project doesn't exist
        """
        project = self._get_project(project_id)
        df = self._get_items_df(project_id, weeks, item_type)
        
        if df.empty:
            return MetricResponse(data=[], stats=MetricStats(avg=0, trend_pct=0), unit="items", period=granularity)
        
        done_col = self._get_done_column(project)
        if not done_col:
            return MetricResponse(data=[], stats=MetricStats(avg=0, trend_pct=0), unit="items", period=granularity)
        
        # Calculate throughput
        result_df = calc_throughput(df, done_col, weeks, granularity=granularity)
        result_df = trim_leading_empty_buckets(result_df)
        
        if result_df.empty:
            return MetricResponse(data=[], stats=MetricStats(avg=0, trend_pct=0), unit="items", period=granularity)
        
        # Format as MetricDataPoint with by_type breakdown
        data_points = []
        totals = []
        for idx, row in result_df.iterrows():
            total = int(row.get("Total", 0))
            # Include breakdown by item type (all columns except 'Total')
            by_type = {col: int(row[col]) for col in result_df.columns if col != "Total"} or None
            totals.append(total)
            data_points.append(MetricDataPoint(
                date=idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx),
                value=float(total),
                by_type=by_type
            ))
        
        # Calculate average and trend
        avg_throughput = float(np.mean(totals)) if totals else 0
        half = len(totals) // 2
        trend_pct = 0.0
        if half > 0 and np.mean(totals[:half]) > 0:
            trend_pct = float((np.mean(totals[half:]) - np.mean(totals[:half])) / np.mean(totals[:half]) * 100)
        
        return MetricResponse(
            data=data_points,
            stats=MetricStats(avg=round(avg_throughput, 1), trend_pct=round(trend_pct, 1)),
            unit="items",
            period=granularity
        )
    
    # ------------------------------------------------------------------
    # Cycle Time Metrics
    # ------------------------------------------------------------------
    
    def cycle_time(self, project_id: int, weeks: int, item_type: str = "all",
                   granularity: str = "week") -> MetricResponse:
        """Calculate median cycle time (days from start to completion).
        
        Args:
            project_id: Project ID
            weeks: Time window in weeks
            item_type: Filter by item type ('all' for no filter)
            granularity: Time bucket (ignored, returns individual items with percentiles)
        
        Returns:
            MetricResponse with cycle time data and percentiles (p50, p85, p95)
        
        Raises:
            ProjectNotFound: If project doesn't exist
        """
        project = self._get_project(project_id)
        df = self._get_items_df(project_id, weeks, item_type)
        
        if df.empty or "cycle_time_days" not in df.columns:
            return MetricResponse(
                data=[],
                stats=MetricStats(avg=0, p50=None, p85=None, p95=None),
                unit="days",
                period="total"
            )
        
        # Calculate percentiles on full dataset
        stats = cycle_time_stats(df)
        
        # Format individual items as data points
        valid = df[df["cycle_time_days"].notna()].copy()
        data_points = []
        
        done_col = self._get_done_column(project)
        for _, row in valid.iterrows():
            completed_at = row.get(done_col, row.get("created_at", None)) if done_col else row.get("created_at", None)
            data_points.append(MetricDataPoint(
                date=completed_at.strftime("%Y-%m-%d") if pd.notna(completed_at) and completed_at is not None else "",
                value=float(row["cycle_time_days"]),
                by_type={"item_key": str(row["item_key"]), "item_type": str(row["item_type"])}
            ))
        
        return MetricResponse(
            data=data_points,
            stats=MetricStats(
                avg=stats.get("p50", 0) or 0,
                p50=stats.get("p50"),
                p85=stats.get("p85"),
                p95=stats.get("p95")
            ),
            unit="days",
            period="total"
        )
    
    # ------------------------------------------------------------------
    # WIP Metrics
    # ------------------------------------------------------------------
    
    def wip(self, project_id: int, weeks: int, item_type: str = "all",
            granularity: str = "week") -> MetricResponse:
        """Calculate Work In Progress over time.
        
        Args:
            project_id: Project ID
            weeks: Time window in weeks
            item_type: Filter by item type ('all' for no filter)
            granularity: Time bucket (ignored for WIP, which uses daily granularity)
        
        Returns:
            MetricResponse with WIP data
        
        Raises:
            ProjectNotFound: If project doesn't exist
        """
        project = self._get_project(project_id)
        df = self._get_items_df(project_id, weeks * 2, item_type)  # Get 2x window for accuracy
        
        if df.empty:
            return MetricResponse(data=[], stats=MetricStats(avg=0), unit="items", period="daily")
        
        # Get workflow steps (wip_over_time needs the step objects, not just done_col)
        if not project.workflow_steps:
            return MetricResponse(data=[], stats=MetricStats(avg=0), unit="items", period="daily")
        
        # Build steps list for wip_over_time function
        steps_list = [
            {
                "display_name": s.display_name,
                "stage": s.stage,
                "position": s.position,
                "source_statuses": s.source_statuses or []
            }
            for s in sorted(project.workflow_steps, key=lambda s: s.position)
        ]
        
        # Calculate WIP (returns daily data)
        result_df = wip_over_time(df, steps_list, weeks=weeks)
        
        if result_df.empty:
            return MetricResponse(data=[], stats=MetricStats(avg=0), unit="items", period="daily")
        
        # Format as MetricDataPoint
        data_points = self._wip_df_to_metric_points(result_df)
        avg_wip = self._calculate_average([p.value for p in data_points]) if data_points else 0
        
        return MetricResponse(
            data=data_points,
            stats=MetricStats(avg=round(avg_wip, 1)),
            unit="items",
            period="daily"
        )
    
    # ------------------------------------------------------------------
    # Flow Efficiency
    # ------------------------------------------------------------------
    
    def flow_efficiency(self, project_id: int, weeks: int, item_type: str = "all",
                       granularity: str = "week") -> MetricResponse:
        """Calculate flow efficiency (active time / total time).
        
        Args:
            project_id: Project ID
            weeks: Time window in weeks
            item_type: Filter by item type ('all' for no filter)
            granularity: Time bucket ('day', 'week', 'biweek', 'month')
        
        Returns:
            MetricResponse with flow efficiency data (0-100%)
        
        Raises:
            ProjectNotFound: If project doesn't exist
        """
        project = self._get_project(project_id)
        df = self._get_items_df(project_id, weeks, item_type)
        
        if df.empty:
            return MetricResponse(data=[], stats=MetricStats(avg=0), unit="%", period=granularity)
        
        done_col = self._get_done_column(project)
        if not done_col:
            return MetricResponse(data=[], stats=MetricStats(avg=0), unit="%", period=granularity)
        
        # Calculate flow efficiency
        result_df = calc_flow_efficiency(df, done_col, weeks, granularity=granularity)
        result_df = trim_leading_empty_buckets(result_df)
        
        if result_df.empty:
            return MetricResponse(data=[], stats=MetricStats(avg=0), unit="%", period=granularity)
        
        # Format as MetricDataPoint
        data_points = self._generic_df_to_metric_points(result_df, "flow_efficiency")
        avg_fe = self._calculate_average([p.value for p in data_points]) if data_points else 0
        
        return MetricResponse(
            data=data_points,
            stats=MetricStats(avg=round(avg_fe, 1)),
            unit="%",
            period=granularity
        )
    
    # ------------------------------------------------------------------
    # Net Flow
    # ------------------------------------------------------------------
    
    def net_flow(self, project_id: int, weeks: int, item_type: str = "all",
                 granularity: str = "week") -> MetricResponse:
        """Calculate net flow (items completed - items added).
        
        Args:
            project_id: Project ID
            weeks: Time window in weeks
            item_type: Filter by item type ('all' for no filter)
            granularity: Time bucket ('day', 'week', 'biweek', 'month')
        
        Returns:
            MetricResponse with net flow data
        
        Raises:
            ProjectNotFound: If project doesn't exist
        """
        project = self._get_project(project_id)
        df = self._get_items_df(project_id, weeks, item_type)
        
        if df.empty:
            return MetricResponse(data=[], stats=MetricStats(avg=0), unit="items", period=granularity)
        
        done_col = self._get_done_column(project)
        if not done_col:
            return MetricResponse(data=[], stats=MetricStats(avg=0), unit="items", period=granularity)
        
        # Calculate net flow
        result_df = calc_net_flow(df, done_col, weeks, granularity=granularity)
        result_df = trim_leading_empty_buckets(result_df)
        
        if result_df.empty:
            return MetricResponse(data=[], stats=MetricStats(avg=0), unit="items", period=granularity)
        
        # Format as MetricDataPoint
        data_points = self._generic_df_to_metric_points(result_df, "net_flow")
        avg_nf = self._calculate_average([p.value for p in data_points]) if data_points else 0
        
        return MetricResponse(
            data=data_points,
            stats=MetricStats(avg=round(avg_nf, 1)),
            unit="items",
            period=granularity
        )
    
    # ------------------------------------------------------------------
    # Private helpers for data retrieval
    # ------------------------------------------------------------------
    
    def _get_project(self, project_id: int) -> Project:
        """Fetch project by ID or raise ProjectNotFound."""
        project = self._db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ProjectNotFound(f"Project {project_id} not found")
        return project
    
    def _get_items_df(self, project_id: int, weeks: int, item_type: str) -> pd.DataFrame:
        """Load cached items into a DataFrame, filtered by date and type."""
        items = self._db.query(CachedItem).filter(CachedItem.project_id == project_id).all()
        if not items:
            return pd.DataFrame()
        
        records = []
        for item in items:
            # Convert ItemTransition objects to list of dicts
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
        
        # Convert date columns to datetime without timezone
        date_cols = [c for c in df.columns if c not in {"item_key", "item_type", "creator", "cycle_time_days", "lead_time_days", "status_transitions"}]
        for col in date_cols:
            try:
                df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
                df[col] = df[col].dt.tz_localize(None)
            except Exception:
                pass
        
        # Filter by item type
        if item_type and item_type != "all":
            df = df[df["item_type"] == item_type]
        
        # Filter by weeks (created_at >= cutoff)
        if weeks and weeks > 0:
            cutoff = _utcnow() - timedelta(weeks=weeks)
            if "created_at" in df.columns:
                df = df[df["created_at"] >= cutoff]
        
        return df
    
    def _get_done_column(self, project: Project) -> Optional[str]:
        """Get the display name of the 'done' workflow step."""
        steps = sorted(project.workflow_steps, key=lambda s: s.position)
        if not steps:
            return None
        
        done_steps = [s for s in steps if s.stage == "done"]
        if done_steps:
            return done_steps[-1].display_name
        
        return steps[-1].display_name if steps else None
    
    # ------------------------------------------------------------------
    # Private helpers for response formatting
    # ------------------------------------------------------------------
    
    def _wip_df_to_metric_points(self, df: pd.DataFrame) -> list[MetricDataPoint]:
        """Convert WIP DataFrame to MetricDataPoint list."""
        points = []
        for _, row in df.iterrows():
            date_val = row.get("date", row.get("week"))
            if isinstance(date_val, pd.Timestamp):
                date_str = date_val.strftime("%Y-%m-%d")
            else:
                date_str = str(date_val)
            
            points.append(MetricDataPoint(
                date=date_str,
                value=int(row.get("count", 0)),
                by_type={"stage": row.get("stage", "")} if "stage" in row else None
            ))
        
        return points
    
    def _quality_df_to_metric_points(self, df: pd.DataFrame) -> list[MetricDataPoint]:
        """Convert quality rate DataFrame to MetricDataPoint list with bug breakdown."""
        df = df.copy()
        df["week"] = df["week"].dt.strftime("%Y-%m-%d")
        
        points = []
        for _, row in df.iterrows():
            points.append(MetricDataPoint(
                date=row["week"],
                value=float(row.get("quality_pct", 0)),
                by_type={
                    "total": int(row.get("total", 0)),
                    "bugs": int(row.get("bugs", 0)),
                }
            ))
        
        return points
    
    def _generic_df_to_metric_points(self, df: pd.DataFrame, metric_col: str = "value") -> list[MetricDataPoint]:
        """Convert generic metric DataFrame to MetricDataPoint list."""
        df = df.copy()
        
        # Format date column if it exists
        if "week" in df.columns:
            df["week"] = df["week"].dt.strftime("%Y-%m-%d")
            date_col = "week"
        elif "date" in df.columns:
            if isinstance(df["date"].iloc[0], pd.Timestamp):
                df["date"] = df["date"].dt.strftime("%Y-%m-%d")
            date_col = "date"
        else:
            # Fallback: use first column as date
            date_col = df.columns[0]
        
        points = []
        for _, row in df.iterrows():
            points.append(MetricDataPoint(
                date=str(row[date_col]),
                value=float(row.get(metric_col, 0))
            ))
        
        return points
    
    def _calculate_average(self, values: list[float]) -> float:
        """Calculate average of values, handling empty list."""
        if not values:
            return 0.0
        return sum(values) / len(values)
