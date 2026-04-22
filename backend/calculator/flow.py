import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Granularity helpers
# ---------------------------------------------------------------------------

_GRANULARITY_MAP: dict[str, str] = {
    "day":    "D",
    "week":   "W-MON",
    "biweek": "2W-MON",
    "month":  "MS",
}

_VALID_GRANULARITIES = frozenset(_GRANULARITY_MAP.keys())


def _resolve_freq(granularity: str) -> str:
    """Return the pandas frequency string for a named granularity."""
    if granularity not in _VALID_GRANULARITIES:
        raise ValueError(
            f"Invalid granularity {granularity!r}. "
            f"Must be one of: {sorted(_VALID_GRANULARITIES)}"
        )
    return _GRANULARITY_MAP[granularity]


def _next_period(date: pd.Timestamp, granularity: str) -> pd.Timestamp:
    """Return the start of the next bucket after ``date``."""
    if granularity == "month":
        return date + pd.DateOffset(months=1)
    elif granularity == "biweek":
        return date + pd.Timedelta(weeks=2)
    elif granularity == "day":
        return date + pd.Timedelta(days=1)
    else:
        return date + pd.Timedelta(weeks=1)

def _naive(series: pd.Series) -> pd.Series:
    """Convert a tz-aware datetime Series to UTC-naive. No-op if already naive."""
    if pd.api.types.is_datetime64_any_dtype(series) and getattr(series.dt, "tz", None) is not None:
        return series.dt.tz_convert("UTC").dt.tz_localize(None)
    return series

def trim_leading_empty_buckets(df: pd.DataFrame) -> pd.DataFrame:
    """Remove leading empty buckets from time-series DataFrame.
    
    A bucket is considered empty if all numeric columns are zero or NaN.
    Preserves the index (typically datetime).
    
    Args:
        df: DataFrame with time-series data (typically indexed by date)
        
    Returns:
        DataFrame with leading empty buckets removed
    """
    if df.empty:
        return df
    
    # Find numeric columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if not numeric_cols:
        return df
    
    # Find first row with any non-zero, non-NaN numeric value
    has_data = ((df[numeric_cols] != 0).any(axis=1)) & (df[numeric_cols].notna().any(axis=1))
    
    if not has_data.any():
        # All rows are empty, return as is
        return df
    
    # Find the first row with data (use idxmax to get the first True)
    first_data_idx = has_data.idxmax() if has_data.any() else df.index[0]
    
    # Return from first data row onward
    if first_data_idx == df.index[0]:
        return df
    
    return df.loc[first_data_idx:]

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
            # Ensure both columns are tz-naive before subtraction to avoid timezone mismatch errors
            df["cycle_time_days"] = (_naive(df[done_col]) - _naive(df[start_col])).dt.days

    first_col = steps[0]["display_name"] if steps else None
    if done_steps and first_col:
        done_col = done_steps[-1]["display_name"]
        if first_col in df.columns and done_col in df.columns:
            # Ensure both columns are tz-naive before subtraction to avoid timezone mismatch errors
            df["lead_time_days"] = (_naive(df[done_col]) - _naive(df[first_col])).dt.days
        elif "created_at" in df.columns and done_col in df.columns:
            # Ensure both columns are tz-naive before subtraction to avoid timezone mismatch errors
            df["lead_time_days"] = (_naive(df[done_col]) - _naive(df["created_at"])).dt.days

    return df


def compute_workflow_timestamps_from_transitions(
    transitions: list,
    workflow_steps: list,
) -> dict:
    """Derive workflow_timestamps from raw status_transitions + current workflow config.

    Arguments:
        transitions: list of {"from_status": str|None, "to_status": str, "transitioned_at": ISO str}
        workflow_steps: list of {"display_name": str, "source_statuses": list, "stage": str, "position": int}

    Returns:
        dict mapping display_name → ISO timestamp string (or None if never reached).

    Semantics:
        - Records the FIRST time an issue reached each workflow step.
        - If an issue is reopened (Done → In Progress → Done again), the first Done
          timestamp is preserved.
    """
    if not transitions or not workflow_steps:
        return {}

    # Build a map: source_status → display_name
    status_to_step = {}
    for step in workflow_steps:
        for source_status in step.get("source_statuses", []):
            status_to_step[source_status] = step["display_name"]

    # Track first arrival at each step
    step_arrivals = {}

    for trans in transitions:
        to_status = trans.get("to_status")
        if not to_status or to_status not in status_to_step:
            continue

        step_name = status_to_step[to_status]
        if step_name not in step_arrivals:
            # First time reaching this step
            step_arrivals[step_name] = trans.get("transitioned_at")

    # Build result: all steps, but only with timestamps if they were reached
    result = {}
    for step in workflow_steps:
        display_name = step["display_name"]
        result[display_name] = step_arrivals.get(display_name)

    return result


def _now() -> pd.Timestamp:
    """Current time as a tz-naive timestamp (avoids pandas 2.x utcnow quirks)."""
    from datetime import datetime
    return pd.Timestamp(datetime.now()).normalize()


def throughput(df: pd.DataFrame, done_col: str, weeks: int = 12, granularity: str = "week") -> pd.DataFrame:
    """Throughput by item type, bucketed by granularity."""
    if df.empty or done_col not in df.columns:
        return pd.DataFrame()

    freq = _resolve_freq(granularity)

    completed = df[df[done_col].notna()].copy()
    if completed.empty:
        return pd.DataFrame()

    completed[done_col] = _naive(completed[done_col])

    end = _now()
    start = end - pd.Timedelta(weeks=weeks)

    completed = completed[(completed[done_col] >= start) & (completed[done_col] < end + pd.Timedelta(days=1))]
    date_range = pd.date_range(start=start, end=end, freq=freq)
    if completed.empty:
        return pd.DataFrame({"Total": 0}, index=date_range)

    completed = completed.set_index(done_col)
    if "item_type" in completed.columns:
        grouped = (
            completed.groupby(["item_type", pd.Grouper(freq=freq)])
            .size()
            .unstack(level=0, fill_value=0)
        )
        grouped.columns.name = None
        grouped["Total"] = grouped.sum(axis=1)
    else:
        grouped = completed.resample(freq).size().to_frame("Total")

    pivot = grouped.reindex(date_range, fill_value=0)
    return pivot


def cycle_time_by_interval(df: pd.DataFrame, done_col: str, weeks: int = 12, granularity: str = "week") -> pd.DataFrame:
    """Average cycle time bucketed by granularity (based on completion date)."""
    if df.empty or done_col not in df.columns or "cycle_time_days" not in df.columns:
        return pd.DataFrame()

    freq = _resolve_freq(granularity)

    completed = df[df[done_col].notna()].copy()
    if completed.empty:
        return pd.DataFrame()

    completed[done_col] = _naive(completed[done_col])

    end = _now()
    start = end - pd.Timedelta(weeks=weeks)

    completed = completed[(completed[done_col] >= start) & (completed[done_col] < end + pd.Timedelta(days=1))]
    if completed.empty:
        return pd.DataFrame()

    date_range = pd.date_range(start=start, end=end, freq=freq)

    completed = completed.set_index(done_col)
    
    def avg_ct(group):
        clean = group["cycle_time_days"].dropna()
        clean = clean[clean > 0]
        return clean.mean() if len(clean) > 0 else np.nan

    grouped = completed.groupby(pd.Grouper(freq=freq)).apply(avg_ct)
    grouped.index.name = "period"

    pivot = grouped.reindex(date_range)
    return pd.DataFrame({"avg_cycle_time": pivot})


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
    # Ensure start_col is tz-naive before subtraction to avoid timezone mismatch errors
    in_progress["age_days"] = (now - _naive(in_progress[start_col])).dt.days
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
    granularity: str = "week",
) -> pd.DataFrame:
    """Percentage of completed items that are NOT bugs/defects, bucketed by granularity.

    Returns a DataFrame with columns: week, total, bugs, quality_pct.
    """
    if df.empty or done_col not in df.columns:
        return pd.DataFrame()

    freq = _resolve_freq(granularity)

    if bug_types is None:
        bug_types = _DEFAULT_BUG_TYPES
    bug_types_lower = frozenset(b.lower() for b in bug_types)

    df = df.copy()
    df[done_col] = _naive(df[done_col])

    end = _now()
    start = end - pd.Timedelta(weeks=weeks)
    date_range = pd.date_range(start=start, end=end, freq=freq)

    completed = df[df[done_col].notna() & (df[done_col] >= start) & (df[done_col] < end + pd.Timedelta(days=1))].copy()
    if "item_type" not in completed.columns:
        completed["item_type"] = "Unknown"

    completed["_is_bug"] = completed["item_type"].str.lower().isin(bug_types_lower)

    results = []
    for date in date_range:
        next_date = _next_period(date, granularity)
        week_mask = (completed[done_col] >= date) & (completed[done_col] < next_date)
        week_df = completed[week_mask]
        total = len(week_df)
        bugs  = int(week_df["_is_bug"].sum())
        quality_pct = round((total - bugs) / total * 100, 1) if total > 0 else 0.0
        results.append({"week": date, "total": total, "bugs": bugs, "quality_pct": quality_pct})

    return pd.DataFrame(results)


def net_flow(df: pd.DataFrame, start_col: str, done_col: str, weeks: int = 12, granularity: str = "week") -> pd.DataFrame:
    """Arrivals minus completions, bucketed by granularity."""
    if df.empty:
        return pd.DataFrame()

    if start_col not in df.columns or done_col not in df.columns:
        return pd.DataFrame()

    freq = _resolve_freq(granularity)

    df = df.copy()
    df[start_col] = _naive(df[start_col])
    df[done_col]  = _naive(df[done_col])

    end = _now()
    start = end - pd.Timedelta(weeks=weeks)
    date_range = pd.date_range(start=start, end=end, freq=freq)

    results = []
    for date in date_range:
        next_date = _next_period(date, granularity)
        arrivals    = len(df[df[start_col].notna() & (df[start_col] >= date) & (df[start_col] < next_date)])
        completions = len(df[df[done_col].notna()  & (df[done_col]  >= date) & (df[done_col]  < next_date)])
        results.append({"week": date, "arrivals": arrivals, "completions": completions, "net": completions - arrivals})

    return pd.DataFrame(results)
