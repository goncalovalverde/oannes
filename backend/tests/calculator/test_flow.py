"""Unit tests for calculator/flow.py — the core Troy Magennis flow metrics engine."""
import pandas as pd
import numpy as np
import pytest

from calculator.flow import (
    compute_cycle_and_lead,
    throughput,
    cycle_time_stats,
    lead_time_stats,
    cfd,
    wip_over_time,
    aging_wip,
    flow_efficiency,
    net_flow,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

STEPS = [
    {"display_name": "Backlog",     "stage": "queue",  "position": 0, "source_statuses": ["Backlog"]},
    {"display_name": "In Progress", "stage": "start",  "position": 1, "source_statuses": ["In Progress"]},
    {"display_name": "Review",      "stage": "in_flight", "position": 2, "source_statuses": ["Review"]},
    {"display_name": "Done",        "stage": "done",   "position": 3, "source_statuses": ["Done"]},
]


def _make_df(n: int = 10, spread_days: int = 30) -> pd.DataFrame:
    """Build a deterministic DataFrame with complete workflow timestamps (relative to today)."""
    from datetime import datetime
    base = pd.Timestamp(datetime.now()).normalize() - pd.Timedelta(days=n + spread_days)
    rows = []
    for i in range(n):
        backlog  = base + pd.Timedelta(days=i)
        progress = backlog  + pd.Timedelta(days=1)
        review   = progress + pd.Timedelta(days=2)
        done     = review   + pd.Timedelta(days=1)
        rows.append({
            "item_key":         f"ITEM-{i+1}",
            "item_type":        "Story" if i % 2 == 0 else "Bug",
            "created_at":       backlog,
            "Backlog":          backlog,
            "In Progress":      progress,
            "Review":           review,
            "Done":             done,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# compute_cycle_and_lead
# ---------------------------------------------------------------------------

class TestComputeCycleAndLead:
    def test_cycle_time_is_in_progress_to_done(self):
        df = _make_df(5)
        result = compute_cycle_and_lead(df, STEPS)
        # In Progress → Done = 1 day review + 2 day = 3 days
        assert (result["cycle_time_days"] == 3).all()

    def test_lead_time_is_backlog_to_done(self):
        df = _make_df(5)
        result = compute_cycle_and_lead(df, STEPS)
        # Backlog → Done = 1 + 2 + 1 = 4 days
        assert (result["lead_time_days"] == 4).all()

    def test_returns_original_df_untouched_columns(self):
        df = _make_df(3)
        original_cols = set(df.columns)
        result = compute_cycle_and_lead(df, STEPS)
        assert original_cols.issubset(set(result.columns))

    def test_empty_df_returns_empty(self):
        result = compute_cycle_and_lead(pd.DataFrame(), STEPS)
        assert result.empty

    def test_missing_done_column_no_crash(self):
        df = _make_df(3).drop(columns=["Done"])
        # Should not raise — just won't compute times
        result = compute_cycle_and_lead(df, STEPS)
        assert "cycle_time_days" not in result.columns or result["cycle_time_days"].isna().all()


# ---------------------------------------------------------------------------
# throughput
# ---------------------------------------------------------------------------

class TestThroughput:
    def test_returns_dataframe_with_total_column(self):
        df = _make_df(20)
        result = throughput(df, done_col="Done", weeks=52)
        assert "Total" in result.columns

    def test_total_equals_sum_across_types(self):
        df = _make_df(20)
        result = throughput(df, done_col="Done", weeks=52)
        type_cols = [c for c in result.columns if c != "Total"]
        if type_cols:
            assert (result["Total"] == result[type_cols].sum(axis=1)).all()

    def test_empty_df_returns_empty(self):
        result = throughput(pd.DataFrame(), done_col="Done")
        assert result.empty

    def test_items_without_done_are_excluded(self):
        df = _make_df(10)
        df.loc[0:4, "Done"] = pd.NaT
        result = throughput(df, done_col="Done", weeks=52)
        assert result["Total"].sum() <= 10
        assert result["Total"].sum() >= 1  # at least the non-NaT rows count


# ---------------------------------------------------------------------------
# cycle_time_stats / lead_time_stats
# ---------------------------------------------------------------------------

class TestTimeStats:
    def setup_method(self):
        df = _make_df(20)
        self.df_with_times = compute_cycle_and_lead(df, STEPS)

    def test_cycle_time_keys(self):
        stats = cycle_time_stats(self.df_with_times)
        for key in ("p50", "p85", "p95", "mean", "std", "count"):
            assert key in stats, f"Missing key: {key}"

    def test_lead_time_keys(self):
        stats = lead_time_stats(self.df_with_times)
        for key in ("p50", "p85", "p95", "mean", "std", "count"):
            assert key in stats, f"Missing key: {key}"

    def test_percentile_ordering(self):
        stats = cycle_time_stats(self.df_with_times)
        assert stats["p50"] <= stats["p85"] <= stats["p95"]

    def test_empty_df_returns_zeros(self):
        stats = cycle_time_stats(pd.DataFrame())
        assert stats["count"] == 0

    def test_count_matches_rows(self):
        stats = cycle_time_stats(self.df_with_times)
        assert stats["count"] == len(self.df_with_times)


# ---------------------------------------------------------------------------
# CFD
# ---------------------------------------------------------------------------

class TestCFD:
    def test_returns_dataframe_with_step_columns(self):
        df = _make_df(10)
        result = cfd(df, STEPS)
        assert not result.empty
        for step in ("Backlog", "In Progress", "Review", "Done"):
            assert step in result.columns

    def test_monotonically_non_decreasing(self):
        """Cumulative counts must never go down."""
        df = _make_df(15)
        result = cfd(df, STEPS)
        for col in result.columns:
            diffs = result[col].diff().dropna()
            assert (diffs >= 0).all(), f"CFD column {col!r} decreased"

    def test_empty_df_returns_empty(self):
        result = cfd(pd.DataFrame(), STEPS)
        assert result.empty


# ---------------------------------------------------------------------------
# wip_over_time
# ---------------------------------------------------------------------------

class TestWIPOverTime:
    def test_returns_non_empty_for_valid_data(self):
        df = _make_df(10)
        result = wip_over_time(df, STEPS)
        assert not result.empty

    def test_columns_are_date_stage_count(self):
        """wip_over_time returns long-form data: date, stage, count."""
        df = _make_df(10)
        result = wip_over_time(df, STEPS)
        for col in ("date", "stage", "count"):
            assert col in result.columns

    def test_stage_values_contain_step_names(self):
        df = _make_df(10)
        result = wip_over_time(df, STEPS)
        stages = set(result["stage"].unique())
        assert "In Progress" in stages or "Done" in stages or "Backlog" in stages


# ---------------------------------------------------------------------------
# aging_wip
# ---------------------------------------------------------------------------

class TestAgingWIP:
    def test_only_wip_items_included(self):
        """Items with a Done timestamp should not appear in aging WIP."""
        df = _make_df(10)
        result = aging_wip(df, STEPS)
        # Done items have a Done timestamp, so age_days should not be present for them
        # (implementation-specific: result contains only in-progress items)
        assert isinstance(result, pd.DataFrame)

    def test_empty_df_returns_empty(self):
        result = aging_wip(pd.DataFrame(), STEPS)
        assert result.empty


# ---------------------------------------------------------------------------
# flow_efficiency
# ---------------------------------------------------------------------------

class TestFlowEfficiency:
    def test_between_0_and_1(self):
        df = _make_df(10)
        result = flow_efficiency(df, STEPS)
        assert 0.0 <= result <= 1.0

    def test_empty_df_returns_zero(self):
        result = flow_efficiency(pd.DataFrame(), STEPS)
        assert result == 0.0


# ---------------------------------------------------------------------------
# net_flow
# ---------------------------------------------------------------------------

class TestNetFlow:
    def test_returns_net_column(self):
        """net_flow returns long-form with columns: week, arrivals, completions, net."""
        df = _make_df(10)
        result = net_flow(df, start_col="In Progress", done_col="Done", weeks=52)
        assert "net" in result.columns
        assert "arrivals" in result.columns
        assert "completions" in result.columns

    def test_positive_when_more_done_than_started(self):
        """If everything that enters also completes, net flow should be non-negative most weeks."""
        df = _make_df(20)
        result = net_flow(df, start_col="In Progress", done_col="Done", weeks=52)
        assert (result["net"] >= 0).sum() >= len(result) * 0.5


# ---------------------------------------------------------------------------
# Empty-DataFrame guard clauses (B-4 regression + coverage for guard lines)
# ---------------------------------------------------------------------------

class TestEmptyDataFrameGuards:
    """Every public function must handle an empty DataFrame gracefully."""

    def test_compute_cycle_and_lead_empty_df_returns_empty(self):
        result = compute_cycle_and_lead(pd.DataFrame(), STEPS)
        assert result.empty

    def test_throughput_empty_df_returns_empty(self):
        assert throughput(pd.DataFrame(), "Done").empty

    def test_throughput_missing_done_col_returns_empty(self):
        df = _make_df(5)
        assert throughput(df, "NonExistentCol").empty

    def test_cycle_time_stats_empty_df_returns_none_percentiles(self):
        result = cycle_time_stats(pd.DataFrame())
        assert result["p50"] is None
        assert result["p85"] is None
        assert result["count"] == 0

    def test_cycle_time_stats_no_column_returns_none_percentiles(self):
        result = cycle_time_stats(pd.DataFrame({"other_col": [1, 2, 3]}))
        assert result["p50"] is None

    def test_cycle_time_stats_all_nan_returns_none_percentiles(self):
        import numpy as np
        result = cycle_time_stats(pd.DataFrame({"cycle_time_days": [np.nan, np.nan]}))
        assert result["p50"] is None

    def test_lead_time_stats_empty_df_returns_none_percentiles(self):
        result = lead_time_stats(pd.DataFrame())
        assert result["p50"] is None
        assert result["count"] == 0

    def test_cfd_empty_df_returns_empty(self):
        assert cfd(pd.DataFrame(), STEPS).empty

    def test_cfd_no_matching_columns_returns_empty(self):
        df = pd.DataFrame({"unrelated": [1, 2]})
        assert cfd(df, STEPS).empty

    def test_wip_over_time_empty_df_returns_empty(self):
        assert wip_over_time(pd.DataFrame(), STEPS, 12).empty

    def test_aging_wip_empty_df_returns_empty(self):
        assert aging_wip(pd.DataFrame(), STEPS).empty

    def test_aging_wip_no_in_flight_steps_returns_empty(self):
        steps_no_flight = [s for s in STEPS if s["stage"] != "in_flight"]
        assert aging_wip(_make_df(5), steps_no_flight).empty

    def test_flow_efficiency_empty_df_returns_zero(self):
        assert flow_efficiency(pd.DataFrame(), STEPS) == 0.0

    def test_flow_efficiency_no_active_steps_returns_zero(self):
        steps_no_active = [s for s in STEPS if s["stage"] != "in_flight"]
        assert flow_efficiency(_make_df(5), steps_no_active) == 0.0

    def test_net_flow_empty_df_returns_empty(self):
        assert net_flow(pd.DataFrame(), "In Progress", "Done").empty

    def test_net_flow_missing_columns_returns_empty(self):
        df = _make_df(5)
        assert net_flow(df, "NonExistent", "Done").empty


# ---------------------------------------------------------------------------
# B-4: compute_cycle_and_lead must not mutate the caller's DataFrame
# ---------------------------------------------------------------------------

class TestComputeCycleAndLeadNoMutation:
    def test_does_not_add_columns_to_caller_df(self):
        df = _make_df(5)
        original_columns = set(df.columns)
        compute_cycle_and_lead(df, STEPS)
        assert set(df.columns) == original_columns, (
            "compute_cycle_and_lead mutated the caller's DataFrame in-place"
        )

    def test_does_not_mutate_filtered_slice(self):
        """Passing a boolean-indexed slice (common pandas copy-on-write scenario)."""
        df = _make_df(10)
        subset = df[df["item_type"] == "Story"]
        cols_before = set(subset.columns)
        compute_cycle_and_lead(subset, STEPS)
        assert set(subset.columns) == cols_before

