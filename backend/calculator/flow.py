import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def _naive(series: pd.Series) -> pd.Series:
    """Convert a tz-aware datetime Series to UTC-naive. No-op if already naive."""
    if pd.api.types.is_datetime64_any_dtype(series) and getattr(series.dt, "tz", None) is not None:
        return series.dt.tz_convert("UTC").dt.tz_localize(None)
    return series

def compute_cycle_and_lead(df: pd.DataFrame, workflow_steps: list) -> pd.DataFrame:
    """Compute cycle_time_days and lead_time_days from workflow step timestamps.

    Returns a new DataFrame — never mutates the caller's copy.
    """
    if df.empty:
        return df

    df = df.copy()  # prevent SettingWithCopyWarning on filtered slices (B-4)

    steps = sorted(workflow_steps, key=lambda s: s.get("position", 0))
    start_steps = [s for s in steps if s["stage"] == "start"]
    done_steps = [s for s in steps if s["stage"] == "done"]

    if start_steps and done_steps:
        start_col = start_steps[0]["display_name"]
        done_col = done_steps[-1]["display_name"]
        if start_col in df.columns and done_col in df.columns:
            df["cycle_time_days"] = (df[done_col] - df[start_col]).dt.days

    first_col = steps[0]["display_name"] if steps else None
    if done_steps and first_col:
        done_col = done_steps[-1]["display_name"]
        if first_col in df.columns and done_col in df.columns:
            df["lead_time_days"] = (df[done_col] - df[first_col]).dt.days
        elif "created_at" in df.columns and done_col in df.columns:
            df["lead_time_days"] = (df[done_col] - df["created_at"]).dt.days

    return df


def _now() -> pd.Timestamp:
    """Current time as a tz-naive timestamp (avoids pandas 2.x utcnow quirks)."""
    from datetime import datetime
    return pd.Timestamp(datetime.now()).normalize()


def throughput(df: pd.DataFrame, done_col: str, weeks: int = 12) -> pd.DataFrame:
    """Weekly throughput by item type."""
    if df.empty or done_col not in df.columns:
        return pd.DataFrame()

    completed = df[df[done_col].notna()].copy()
    if completed.empty:
        return pd.DataFrame()

    completed[done_col] = _naive(completed[done_col])

    end = _now()
    start = end - pd.Timedelta(weeks=weeks)

    # Filter to the requested window before pivoting
    completed = completed[(completed[done_col] >= start) & (completed[done_col] <= end)]
    date_range = pd.date_range(start=start, end=end, freq="W-MON")
    if completed.empty:
        return pd.DataFrame({"Total": 0}, index=date_range)

    # Use resample so the index uses the same Monday anchor as date_range(freq="W-MON")
    completed = completed.set_index(done_col)
    if "item_type" in completed.columns:
        weekly = (
            completed.groupby(["item_type", pd.Grouper(freq="W-MON")])
            .size()
            .unstack(level=0, fill_value=0)
        )
        weekly.columns.name = None
        weekly["Total"] = weekly.sum(axis=1)
    else:
        weekly = completed.resample("W-MON").size().to_frame("Total")

    pivot = weekly.reindex(date_range, fill_value=0)
    return pivot


def cycle_time_stats(df: pd.DataFrame) -> dict:
    """Percentile statistics for cycle time."""
    if df.empty or "cycle_time_days" not in df.columns:
        return {"p50": None, "p85": None, "p95": None, "mean": None, "std": None, "count": 0}

    clean = df["cycle_time_days"].dropna()
    clean = clean[clean > 0]
    if clean.empty:
        return {"p50": None, "p85": None, "p95": None, "mean": None, "std": None, "count": 0}

    return {
        "p50":   float(np.percentile(clean, 50)),
        "p85":   float(np.percentile(clean, 85)),
        "p95":   float(np.percentile(clean, 95)),
        "mean":  float(clean.mean()),
        "std":   float(clean.std()),
        "count": int(len(clean)),
    }


def lead_time_stats(df: pd.DataFrame) -> dict:
    """Percentile statistics for lead time."""
    if df.empty or "lead_time_days" not in df.columns:
        return {"p50": None, "p85": None, "p95": None, "mean": None, "std": None, "count": 0}

    clean = df["lead_time_days"].dropna()
    clean = clean[clean > 0]
    if clean.empty:
        return {"p50": None, "p85": None, "p95": None, "mean": None, "std": None, "count": 0}

    return {
        "p50":   float(np.percentile(clean, 50)),
        "p85":   float(np.percentile(clean, 85)),
        "p95":   float(np.percentile(clean, 95)),
        "mean":  float(clean.mean()),
        "std":   float(clean.std()),
        "count": int(len(clean)),
    }


def cfd(df: pd.DataFrame, workflow_steps: list) -> pd.DataFrame:
    """Cumulative flow diagram data."""
    if df.empty:
        return pd.DataFrame()

    steps = sorted(workflow_steps, key=lambda s: s.get("position", 0))
    step_cols = [s["display_name"] for s in steps if s["display_name"] in df.columns]

    if not step_cols:
        return pd.DataFrame()

    date_cols = df[step_cols].copy()
    for col in step_cols:
        date_cols[col] = pd.to_datetime(date_cols[col], errors="coerce")

    date_cols = date_cols.bfill(axis=1)

    all_dates = pd.concat([date_cols[c] for c in step_cols]).dropna()
    if all_dates.empty:
        return pd.DataFrame()

    date_range = pd.date_range(
        start=all_dates.min().normalize(),
        end=all_dates.max().normalize(),
        freq="D"
    )
    cfd_data = pd.DataFrame(index=date_range)

    for col in step_cols:
        counts = date_cols[col].dropna().dt.normalize().value_counts()
        series = counts.reindex(date_range, fill_value=0).cumsum()
        cfd_data[col] = series

    cfd_data = cfd_data.ffill().fillna(0)
    return cfd_data


def wip_over_time(df: pd.DataFrame, workflow_steps: list, weeks: int = 12) -> pd.DataFrame:
    """WIP per stage per day."""
    if df.empty:
        return pd.DataFrame()

    # Normalize all datetime columns to tz-naive for consistent comparison
    df = df.copy()
    for col in df.select_dtypes(include=["datetimetz"]).columns:
        df[col] = _naive(df[col])

    steps = sorted(workflow_steps, key=lambda s: s.get("position", 0))
    end = _now()
    start = end - pd.Timedelta(weeks=weeks)
    date_range = pd.date_range(start=start, end=end, freq="D")

    results = []
    for date in date_range:
        for step in steps:
            step_col = step["display_name"]
            if step_col not in df.columns:
                continue

            entered = df[df[step_col].notna() & (df[step_col] <= date)]
            next_steps = [s for s in steps if s.get("position", 0) > step.get("position", 0)]
            if next_steps:
                next_col = next_steps[0]["display_name"]
                if next_col in df.columns:
                    exited = df[df[next_col].notna() & (df[next_col] <= date)]
                    in_stage = len(entered) - len(exited)
                else:
                    in_stage = len(entered)
            else:
                in_stage = len(entered)

            results.append({"date": date, "stage": step["display_name"], "count": max(0, in_stage)})

    return pd.DataFrame(results)


def aging_wip(df: pd.DataFrame, workflow_steps: list) -> pd.DataFrame:
    """Current in-flight items with age in days."""
    if df.empty:
        return pd.DataFrame()

    steps = sorted(workflow_steps, key=lambda s: s.get("position", 0))
    in_flight_steps = [s for s in steps if s["stage"] == "in_flight"]
    done_steps = [s for s in steps if s["stage"] == "done"]

    if not in_flight_steps:
        return pd.DataFrame()

    start_col = in_flight_steps[0]["display_name"]
    if start_col not in df.columns:
        return pd.DataFrame()

    in_progress = df[df[start_col].notna()].copy()

    if done_steps:
        done_col = done_steps[-1]["display_name"]
        if done_col in df.columns:
            in_progress = in_progress[in_progress[done_col].isna()]

    now = _now()
    in_progress["age_days"] = (now - in_progress[start_col]).dt.days
    return in_progress


def flow_efficiency(df: pd.DataFrame, workflow_steps: list) -> float:
    """Ratio of active (in_flight) time to total lead time."""
    if df.empty:
        return 0.0

    steps = sorted(workflow_steps, key=lambda s: s.get("position", 0))
    active_steps = [s for s in steps if s["stage"] == "in_flight"]

    if not steps or not active_steps:
        return 0.0

    first_col = steps[0]["display_name"]
    last_col = steps[-1]["display_name"]

    if first_col not in df.columns or last_col not in df.columns:
        return 0.0

    completed = df[df[first_col].notna() & df[last_col].notna()].copy()
    if completed.empty:
        return 0.0

    total_active = 0.0
    total_lead = 0.0

    for _, row in completed.iterrows():
        if pd.notna(row[last_col]) and pd.notna(row[first_col]):
            total_lead += (row[last_col] - row[first_col]).total_seconds() / 86400

        active = 0.0
        for step in active_steps:
            sc = step["display_name"]
            if sc not in df.columns or not pd.notna(row.get(sc)):
                continue
            next_s = [s for s in steps if s.get("position", 0) > step.get("position", 0)]
            if next_s:
                nc = next_s[0]["display_name"]
                if nc in df.columns and pd.notna(row.get(nc)):
                    active += (row[nc] - row[sc]).total_seconds() / 86400
        total_active += active

    return round(min(total_active / total_lead, 1.0), 3) if total_lead > 0 else 0.0


_DEFAULT_BUG_TYPES = frozenset({"bug", "defect", "incident", "hotfix"})


def quality_rate(
    df: pd.DataFrame,
    done_col: str,
    weeks: int = 12,
    bug_types: frozenset | set | None = None,
) -> pd.DataFrame:
    """Weekly percentage of completed items that are NOT bugs/defects.

    Returns a DataFrame with columns: week, total, bugs, quality_pct.
    Rows span the full ``weeks`` window even if a week has zero completions.
    """
    if df.empty or done_col not in df.columns:
        return pd.DataFrame()

    if bug_types is None:
        bug_types = _DEFAULT_BUG_TYPES
    bug_types_lower = frozenset(b.lower() for b in bug_types)

    df = df.copy()
    df[done_col] = _naive(df[done_col])

    end = _now()
    start = end - pd.Timedelta(weeks=weeks)
    date_range = pd.date_range(start=start, end=end, freq="W-MON")

    completed = df[df[done_col].notna() & (df[done_col] >= start) & (df[done_col] <= end)].copy()
    if "item_type" not in completed.columns:
        completed["item_type"] = "Unknown"

    completed["_is_bug"] = completed["item_type"].str.lower().isin(bug_types_lower)

    results = []
    for date in date_range:
        next_date = date + pd.Timedelta(weeks=1)
        week_mask = (completed[done_col] >= date) & (completed[done_col] < next_date)
        week_df = completed[week_mask]
        total = len(week_df)
        bugs  = int(week_df["_is_bug"].sum())
        quality_pct = round((total - bugs) / total * 100, 1) if total > 0 else 0.0
        results.append({"week": date, "total": total, "bugs": bugs, "quality_pct": quality_pct})

    return pd.DataFrame(results)


def net_flow(df: pd.DataFrame, start_col: str, done_col: str, weeks: int = 12) -> pd.DataFrame:
    """Weekly arrivals minus completions."""
    if df.empty:
        return pd.DataFrame()

    if start_col not in df.columns or done_col not in df.columns:
        return pd.DataFrame()

    df = df.copy()
    df[start_col] = _naive(df[start_col])
    df[done_col]  = _naive(df[done_col])

    end = _now()
    start = end - pd.Timedelta(weeks=weeks)
    date_range = pd.date_range(start=start, end=end, freq="W-MON")

    results = []
    for date in date_range:
        next_date = date + pd.Timedelta(weeks=1)
        arrivals    = len(df[df[start_col].notna() & (df[start_col] >= date) & (df[start_col] < next_date)])
        completions = len(df[df[done_col].notna()  & (df[done_col]  >= date) & (df[done_col]  < next_date)])
        results.append({"week": date, "arrivals": arrivals, "completions": completions, "net": completions - arrivals})

    return pd.DataFrame(results)
