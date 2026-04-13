"""Tests for CSVConnector — file parsing, column validation, workflow mapping."""
import os
import textwrap
import tempfile

import pandas as pd
import pytest

from connectors.csv_connector import CSVConnector


STEPS = [
    {"display_name": "Backlog",     "stage": "queue",  "position": 0, "source_statuses": ["Backlog"]},
    {"display_name": "In Progress", "stage": "start",  "position": 1, "source_statuses": ["In Progress"]},
    {"display_name": "Done",        "stage": "done",   "position": 2, "source_statuses": ["Done"]},
]


def _write_csv(content: str) -> str:
    """Write content to a temp CSV file and return its path."""
    tf = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
    tf.write(textwrap.dedent(content).strip())
    tf.close()
    return tf.name


@pytest.fixture()
def valid_csv():
    path = _write_csv("""
        item_key,item_type,created_at,Backlog,In Progress,Done
        ITEM-1,Story,2024-01-01,2024-01-01,2024-01-02,2024-01-05
        ITEM-2,Bug,  2024-01-03,2024-01-03,2024-01-04,2024-01-06
        ITEM-3,Story,2024-01-05,2024-01-05,2024-01-07,2024-01-10
    """)
    yield path
    os.unlink(path)


@pytest.fixture()
def csv_missing_columns():
    path = _write_csv("""
        item_key,item_type
        ITEM-1,Story
    """)
    yield path
    os.unlink(path)


@pytest.fixture()
def csv_bad_dates():
    path = _write_csv("""
        item_key,item_type,created_at,Backlog,In Progress,Done
        ITEM-1,Story,not-a-date,also-bad,bad2,bad3
    """)
    yield path
    os.unlink(path)


@pytest.fixture()
def csv_wip_only():
    """Items in progress but not done yet."""
    path = _write_csv("""
        item_key,item_type,created_at,Backlog,In Progress,Done
        ITEM-1,Story,2024-01-01,2024-01-01,2024-01-02,
        ITEM-2,Bug,  2024-01-03,2024-01-03,2024-01-04,
    """)
    yield path
    os.unlink(path)


# ---------------------------------------------------------------------------
# test_connection
# ---------------------------------------------------------------------------

class TestTestConnection:
    def test_valid_file_returns_success(self, valid_csv):
        conn = CSVConnector({"file_path": valid_csv}, STEPS)
        result = conn.test_connection()
        assert result["success"] is True
        assert "Columns" in result["message"]

    def test_missing_file_returns_failure(self):
        conn = CSVConnector({"file_path": "/nonexistent/path.csv"}, STEPS)
        result = conn.test_connection()
        assert result["success"] is False
        assert "not found" in result["message"].lower() or "file" in result["message"].lower()

    def test_missing_required_columns_returns_failure(self, csv_missing_columns):
        conn = CSVConnector({"file_path": csv_missing_columns}, STEPS)
        result = conn.test_connection()
        assert result["success"] is False
        assert "missing" in result["message"].lower() or "column" in result["message"].lower()

    def test_no_file_path_in_config(self):
        conn = CSVConnector({}, STEPS)
        result = conn.test_connection()
        assert result["success"] is False


# ---------------------------------------------------------------------------
# fetch_items
# ---------------------------------------------------------------------------

class TestFetchItems:
    def test_returns_dataframe(self, valid_csv):
        conn = CSVConnector({"file_path": valid_csv}, STEPS)
        df = conn.fetch_items()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3

    def test_required_columns_present(self, valid_csv):
        conn = CSVConnector({"file_path": valid_csv}, STEPS)
        df = conn.fetch_items()
        for col in ("item_key", "item_type", "created_at"):
            assert col in df.columns

    def test_workflow_timestamps_populated(self, valid_csv):
        conn = CSVConnector({"file_path": valid_csv}, STEPS)
        df = conn.fetch_items()
        # Every row should have a workflow_timestamps dict
        assert "workflow_timestamps" in df.columns
        assert all(isinstance(v, dict) for v in df["workflow_timestamps"])

    def test_done_items_have_cycle_time(self, valid_csv):
        conn = CSVConnector({"file_path": valid_csv}, STEPS)
        df = conn.fetch_items()
        assert "cycle_time_days" in df.columns
        # All items have done dates, so no NaN cycle times
        assert df["cycle_time_days"].notna().all()

    def test_wip_items_have_no_cycle_time(self, csv_wip_only):
        conn = CSVConnector({"file_path": csv_wip_only}, STEPS)
        df = conn.fetch_items()
        # No Done dates → cycle time should be None/NaN
        ct = df.get("cycle_time_days")
        if ct is not None:
            assert ct.isna().all() or (ct == 0).all()

    def test_bad_dates_produce_nat_not_crash(self, csv_bad_dates):
        conn = CSVConnector({"file_path": csv_bad_dates}, STEPS)
        # Should not raise
        df = conn.fetch_items()
        assert isinstance(df, pd.DataFrame)

    def test_empty_file_returns_empty_df(self):
        path = _write_csv("item_key,item_type,created_at,Backlog,In Progress,Done\n")
        try:
            conn = CSVConnector({"file_path": path}, STEPS)
            df = conn.fetch_items()
            assert df.empty or len(df) == 0
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# discover_statuses
# ---------------------------------------------------------------------------

class TestDiscoverStatuses:
    def test_returns_list(self, valid_csv):
        conn = CSVConnector({"file_path": valid_csv}, STEPS)
        statuses = conn.discover_statuses("csv")
        assert isinstance(statuses, list)

    def test_excludes_standard_columns(self, valid_csv):
        conn = CSVConnector({"file_path": valid_csv}, STEPS)
        statuses = conn.discover_statuses("csv")
        standard = {"item_key", "item_type", "creator", "created_at", "cycle_time_days", "lead_time_days"}
        for s in statuses:
            assert s not in standard

    def test_includes_workflow_columns(self, valid_csv):
        conn = CSVConnector({"file_path": valid_csv}, STEPS)
        statuses = conn.discover_statuses("csv")
        assert "Backlog" in statuses or "In Progress" in statuses or "Done" in statuses
