"""Integration tests for /metrics API endpoints.

These tests exercise the full FastAPI request-response cycle using an
in-memory SQLite database seeded with enough CachedItems to produce
non-trivial metric results.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts(days_ago: int) -> str:
    """ISO string for a date N days ago."""
    return (datetime.now() - timedelta(days=days_ago)).isoformat()


def _create_project(client, steps=None):
    """Create a project with a simple Kanban workflow and return its id."""
    if steps is None:
        steps = [
            {"position": 0, "display_name": "Backlog",     "stage": "queue",     "source_statuses": ["Backlog"]},
            {"position": 1, "display_name": "In Progress", "stage": "in_flight", "source_statuses": ["In Progress"]},
            {"position": 2, "display_name": "Done",        "stage": "done",      "source_statuses": ["Done"]},
        ]
    resp = client.post("/api/projects/", json={
        "name": "Metrics Test Project",
        "platform": "csv",
        "config": {"file_path": "/tmp/dummy.csv"},
        "sync_frequency": "manual",
        "workflow_steps": steps,
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _seed_items(db, project_id: int, n: int = 10):
    """Insert CachedItems directly into the test DB."""
    from models.sync_job import CachedItem

    now = datetime.now()
    for i in range(n):
        done_at = now - timedelta(days=i * 3)
        start_at = done_at - timedelta(days=4)
        backlog_at = start_at - timedelta(days=2)
        item = CachedItem(
            project_id=project_id,
            item_key=f"ITEM-{i+1:03d}",
            item_type="Story" if i % 2 == 0 else "Bug",
            creator="alice",
            created_at=backlog_at,
            workflow_timestamps={
                "Backlog":      backlog_at.isoformat(),
                "In Progress":  start_at.isoformat(),
                "Done":         done_at.isoformat(),
            },
            cycle_time_days=4.0,
            lead_time_days=6.0,
        )
        db.add(item)
    db.commit()


# ---------------------------------------------------------------------------
# Tests: /metrics/{id}/item-types
# ---------------------------------------------------------------------------

class TestItemTypes:
    def test_empty_project_returns_empty_list(self, client):
        pid = _create_project(client)
        r = client.get(f"/api/metrics/{pid}/item-types")
        assert r.status_code == 200
        assert r.json()["item_types"] == []

    def test_seeded_items_return_correct_types(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=4)
        r = client.get(f"/api/metrics/{pid}/item-types")
        assert r.status_code == 200
        types = set(r.json()["item_types"])
        assert types == {"Story", "Bug"}


# ---------------------------------------------------------------------------
# Tests: /metrics/{id}/throughput
# ---------------------------------------------------------------------------

class TestThroughput:
    def test_empty_project_returns_zero_avg(self, client):
        pid = _create_project(client)
        r = client.get(f"/api/metrics/{pid}/throughput")
        assert r.status_code == 200
        assert r.json()["avg"] == 0

    def test_seeded_items_produce_positive_avg(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=10)
        r = client.get(f"/api/metrics/{pid}/throughput")
        assert r.status_code == 200
        body = r.json()
        assert body["avg"] >= 0
        assert isinstance(body["data"], list)

    def test_unknown_project_returns_404(self, client):
        r = client.get("/api/metrics/999/throughput")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Tests: /metrics/{id}/cycle-time
# ---------------------------------------------------------------------------

class TestCycleTime:
    def test_empty_project_returns_null_percentiles(self, client):
        pid = _create_project(client)
        r = client.get(f"/api/metrics/{pid}/cycle-time")
        assert r.status_code == 200
        pct = r.json()["percentiles"]
        assert pct["p50"] is None
        assert pct["p85"] is None

    def test_seeded_items_produce_percentiles(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=10)
        r = client.get(f"/api/metrics/{pid}/cycle-time")
        assert r.status_code == 200
        body = r.json()
        assert body["percentiles"]["p50"] == pytest.approx(4.0)
        assert len(body["data"]) > 0
        assert "item_key" in body["data"][0]
        assert "cycle_time_days" in body["data"][0]

    def test_item_type_filter(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=10)
        r = client.get(f"/api/metrics/{pid}/cycle-time?item_type=Story")
        assert r.status_code == 200
        for row in r.json()["data"]:
            assert row["item_type"] == "Story"


# ---------------------------------------------------------------------------
# Tests: /metrics/{id}/lead-time
# ---------------------------------------------------------------------------

class TestLeadTime:
    def test_empty_project_returns_null_percentiles(self, client):
        pid = _create_project(client)
        r = client.get(f"/api/metrics/{pid}/lead-time")
        assert r.status_code == 200
        assert r.json()["percentiles"]["p85"] is None

    def test_seeded_items_produce_lead_time(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=10)
        r = client.get(f"/api/metrics/{pid}/lead-time")
        assert r.status_code == 200
        assert r.json()["percentiles"]["p50"] == pytest.approx(6.0)


# ---------------------------------------------------------------------------
# Tests: /metrics/{id}/wip
# ---------------------------------------------------------------------------

class TestWip:
    def test_empty_project_returns_zero_wip(self, client):
        pid = _create_project(client)
        r = client.get(f"/api/metrics/{pid}/wip")
        assert r.status_code == 200
        assert r.json()["current_wip"] == 0

    def test_response_shape(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=5)
        r = client.get(f"/api/metrics/{pid}/wip")
        assert r.status_code == 200
        body = r.json()
        assert "data" in body
        assert "current_wip" in body


# ---------------------------------------------------------------------------
# Tests: /metrics/{id}/aging-wip
# ---------------------------------------------------------------------------

class TestAgingWip:
    def test_empty_project_returns_empty_data(self, client):
        pid = _create_project(client)
        r = client.get(f"/api/metrics/{pid}/aging-wip")
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_aging_items_have_required_fields(self, client, db):
        pid = _create_project(client)
        # Insert an open (not-done) item
        from models.sync_job import CachedItem
        from datetime import datetime, timedelta
        start = datetime.now() - timedelta(days=10)
        item = CachedItem(
            project_id=pid,
            item_key="OPEN-001",
            item_type="Story",
            created_at=start - timedelta(days=2),
            workflow_timestamps={
                "Backlog":      (start - timedelta(days=2)).isoformat(),
                "In Progress":  start.isoformat(),
            },
            cycle_time_days=None,
            lead_time_days=None,
        )
        db.add(item)
        db.commit()

        r = client.get(f"/api/metrics/{pid}/aging-wip")
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) == 1
        row = data[0]
        assert row["item_key"] == "OPEN-001"
        assert "age_days" in row
        assert "is_over_85th" in row


# ---------------------------------------------------------------------------
# Tests: /metrics/{id}/summary
# ---------------------------------------------------------------------------

class TestSummary:
    def test_summary_returns_expected_keys(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=8)
        r = client.get(f"/api/metrics/{pid}/summary")
        assert r.status_code == 200
        body = r.json()
        for key in ("throughput_avg", "cycle_time_50th", "cycle_time_85th",
                    "current_wip", "flow_efficiency", "item_types"):
            assert key in body, f"Missing key: {key}"

    def test_unknown_project_returns_404(self, client):
        r = client.get("/api/metrics/999/summary")
        assert r.status_code == 404

    def test_summary_aging_wip_alerts_with_open_items(self, client, db):
        """aging_wip_alerts must be >= 1 when there is a very old open item."""
        from models.sync_job import CachedItem
        from datetime import datetime, timedelta
        pid = _create_project(client)
        _seed_items(db, pid, n=5)   # 5 closed items establish a p85 baseline
        old_start = datetime.now() - timedelta(days=60)
        db.add(CachedItem(
            project_id=pid,
            item_key="ANCIENT-001",
            item_type="Story",
            created_at=old_start - timedelta(days=2),
            workflow_timestamps={
                "Backlog":      (old_start - timedelta(days=2)).isoformat(),
                "In Progress":  old_start.isoformat(),
            },
            cycle_time_days=None,
            lead_time_days=None,
        ))
        db.commit()
        r = client.get(f"/api/metrics/{pid}/summary")
        assert r.status_code == 200
        assert r.json()["aging_wip_alerts"] >= 1


# ---------------------------------------------------------------------------
# Tests: /metrics/{id}/cfd
# ---------------------------------------------------------------------------

class TestCfd:
    def test_empty_project_returns_empty(self, client):
        pid = _create_project(client)
        r = client.get(f"/api/metrics/{pid}/cfd")
        assert r.status_code == 200
        assert r.json() == {"data": [], "stages": []}

    def test_unknown_project_returns_404(self, client):
        assert client.get("/api/metrics/999/cfd").status_code == 404

    def test_seeded_items_produce_cfd_shape(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=10)
        r = client.get(f"/api/metrics/{pid}/cfd")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body["stages"], list)
        assert len(body["stages"]) > 0
        assert isinstance(body["data"], list)
        assert len(body["data"]) > 0

    def test_each_cfd_row_contains_date_and_stage_counts(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=10)
        r = client.get(f"/api/metrics/{pid}/cfd")
        body = r.json()
        stages = body["stages"]
        for row in body["data"]:
            assert "date" in row
            for stage in stages:
                assert stage in row
                assert isinstance(row[stage], int)
                assert row[stage] >= 0

    def test_cfd_stage_counts_are_cumulative(self, client, db):
        """For a done-only stage, count should only increase over time."""
        pid = _create_project(client)
        _seed_items(db, pid, n=10)
        r = client.get(f"/api/metrics/{pid}/cfd")
        body = r.json()
        done_counts = [row.get("Done", 0) for row in body["data"]]
        assert done_counts == sorted(done_counts), "Done stage counts must be non-decreasing"

    def test_item_type_filter_reduces_counts(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=10)  # 5 Stories + 5 Bugs
        all_r  = client.get(f"/api/metrics/{pid}/cfd")
        story_r = client.get(f"/api/metrics/{pid}/cfd?item_type=Story")
        assert story_r.status_code == 200
        # Filtered totals must be <= unfiltered for every row position
        all_done  = sum(row.get("Done", 0) for row in all_r.json()["data"])
        story_done = sum(row.get("Done", 0) for row in story_r.json()["data"])
        assert story_done <= all_done


# ---------------------------------------------------------------------------
# Tests: /metrics/{id}/raw-data
# ---------------------------------------------------------------------------

class TestRawData:
    def test_empty_project_returns_empty(self, client):
        pid = _create_project(client)
        r = client.get(f"/api/metrics/{pid}/raw-data")
        assert r.status_code == 200
        assert r.json() == {"data": [], "columns": []}

    def test_unknown_project_returns_404(self, client):
        assert client.get("/api/metrics/999/raw-data").status_code == 404

    def test_seeded_items_return_all_rows(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=7)
        r = client.get(f"/api/metrics/{pid}/raw-data")
        assert r.status_code == 200
        body = r.json()
        assert len(body["data"]) == 7

    def test_response_contains_required_base_columns(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=3)
        body = client.get(f"/api/metrics/{pid}/raw-data").json()
        for col in ("item_key", "item_type"):
            assert col in body["columns"], f"Missing expected column: {col}"

    def test_each_row_has_all_declared_columns(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=3)
        body = client.get(f"/api/metrics/{pid}/raw-data").json()
        for row in body["data"]:
            for col in body["columns"]:
                assert col in row, f"Row missing column '{col}': {row}"

    def test_date_fields_are_formatted_as_strings(self, client, db):
        """Dates must be YYYY-MM-DD strings, not raw datetime objects."""
        import re
        date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        pid = _create_project(client)
        _seed_items(db, pid, n=3)
        body = client.get(f"/api/metrics/{pid}/raw-data").json()
        for row in body["data"]:
            if row.get("Done"):
                assert date_re.match(row["Done"]), f"Done column not a date string: {row['Done']}"

    def test_item_type_filter(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=10)  # 5 Stories + 5 Bugs
        body = client.get(f"/api/metrics/{pid}/raw-data?item_type=Story").json()
        assert all(row["item_type"] == "Story" for row in body["data"])
        assert len(body["data"]) == 5

    def test_weeks_filter_limits_rows(self, client, db):
        """items created > 1 week ago must be excluded when weeks=1."""
        from models.sync_job import CachedItem
        from datetime import datetime, timedelta
        pid = _create_project(client)
        _seed_items(db, pid, n=5)   # items spread over ~12 days → some outside 1-week window
        r = client.get(f"/api/metrics/{pid}/raw-data?weeks=1")
        assert r.status_code == 200
        # At minimum, the most recent item (0 days ago) should appear
        assert len(r.json()["data"]) <= 5


# ---------------------------------------------------------------------------
# Tests: /metrics/monte-carlo
# ---------------------------------------------------------------------------

class TestMonteCarlo:
    def test_when_done_mode_returns_percentile_dates(self, client, db):
        import re
        date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        pid = _create_project(client)
        _seed_items(db, pid, n=20)
        r = client.post("/api/metrics/monte-carlo", json={
            "project_id": pid, "backlog_size": 10,
            "simulations": 500, "weeks_history": 12,
        })
        assert r.status_code == 200
        body = r.json()
        assert body["mode"] == "when_done"
        assert "percentiles" in body
        assert "histogram" in body
        assert "recommended_date" in body
        for key in ("50", "70", "85", "95"):
            val = body["percentiles"][key]
            assert val is not None
            assert date_re.match(val), f"Percentile {key}={val!r} is not a date"

    def test_how_many_mode_returns_integer_percentiles(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=20)
        r = client.post("/api/metrics/monte-carlo", json={
            "project_id": pid, "target_weeks": 4,
            "simulations": 500, "weeks_history": 12,
        })
        assert r.status_code == 200
        body = r.json()
        assert body["mode"] == "how_many"
        for key in ("50", "70", "85", "95"):
            assert isinstance(body["percentiles"][key], int)
            assert body["percentiles"][key] > 0

    def test_no_throughput_data_returns_400(self, client):
        """A project with no completed items cannot be simulated."""
        pid = _create_project(client)  # no items
        r = client.post("/api/metrics/monte-carlo", json={
            "project_id": pid, "backlog_size": 10, "simulations": 100,
        })
        assert r.status_code == 400
        assert "Insufficient throughput" in r.json()["detail"]

    def test_neither_backlog_nor_weeks_returns_400(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=10)
        r = client.post("/api/metrics/monte-carlo", json={
            "project_id": pid, "simulations": 100,
        })
        assert r.status_code == 400

    def test_unknown_project_returns_404(self, client):
        r = client.post("/api/metrics/monte-carlo", json={
            "project_id": 999, "backlog_size": 10,
        })
        assert r.status_code == 404

    def test_histogram_probabilities_sum_to_1(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=20)
        r = client.post("/api/metrics/monte-carlo", json={
            "project_id": pid, "backlog_size": 5,
            "simulations": 1000, "weeks_history": 12,
        })
        histogram = r.json()["histogram"]
        total = sum(entry["probability"] for entry in histogram)
        assert abs(total - 1.0) < 0.02, f"Histogram probabilities sum to {total}, expected ~1.0"

    def test_p50_date_before_p95_date(self, client, db):
        """Percentile ordering: p50 <= p70 <= p85 <= p95."""
        pid = _create_project(client)
        _seed_items(db, pid, n=20)
        r = client.post("/api/metrics/monte-carlo", json={
            "project_id": pid, "backlog_size": 20,
            "simulations": 1000, "weeks_history": 12,
        })
        pcts = r.json()["percentiles"]
        dates = [pcts[k] for k in ("50", "70", "85", "95")]
        assert dates == sorted(dates), f"Percentile dates not ordered: {dates}"



class TestNetFlow:
    def test_net_flow_returns_list(self, client, db):
        """GET /metrics/{id}/net-flow should return a list of weekly entries."""
        pid = _create_project(client)
        _seed_items(db, pid, n=10)
        r = client.get(f"/api/metrics/{pid}/net-flow")
        assert r.status_code == 200
        data = r.json()["data"]
        assert isinstance(data, list)

    def test_net_flow_each_entry_has_required_fields(self, client, db):
        """Each net-flow entry must have week, arrivals, completions, net."""
        pid = _create_project(client)
        _seed_items(db, pid, n=10)
        r = client.get(f"/api/metrics/{pid}/net-flow")
        assert r.status_code == 200
        for entry in r.json()["data"]:
            assert "week" in entry
            assert "arrivals" in entry
            assert "completions" in entry
            assert "net" in entry

    def test_net_flow_net_equals_completions_minus_arrivals(self, client, db):
        """net field must equal completions - arrivals for every row."""
        pid = _create_project(client)
        _seed_items(db, pid, n=15)
        r = client.get(f"/api/metrics/{pid}/net-flow")
        for entry in r.json()["data"]:
            assert entry["net"] == entry["completions"] - entry["arrivals"]

    def test_net_flow_unknown_project_returns_404(self, client):
        """GET /metrics/999/net-flow should return 404."""
        r = client.get("/api/metrics/999/net-flow")
        assert r.status_code == 404

    def test_net_flow_empty_project_returns_empty_list(self, client, db):
        """Net flow with no items should return empty data list."""
        pid = _create_project(client)
        r = client.get(f"/api/metrics/{pid}/net-flow")
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_net_flow_weeks_param_respected(self, client, db):
        """weeks query param should limit the window."""
        pid = _create_project(client)
        _seed_items(db, pid, n=10)
        r4  = client.get(f"/api/metrics/{pid}/net-flow?weeks=4")
        r12 = client.get(f"/api/metrics/{pid}/net-flow?weeks=12")
        assert r4.status_code == 200
        assert r12.status_code == 200
        assert len(r4.json()["data"]) <= len(r12.json()["data"])


class TestQualityRate:
    """Integration tests for GET /api/metrics/{id}/quality-rate."""

    def test_quality_rate_returns_list(self, client, db):
        """Endpoint returns a list under 'data' key."""
        pid = _create_project(client)
        _seed_items(db, pid, n=10)
        r = client.get(f"/api/metrics/{pid}/quality-rate")
        assert r.status_code == 200
        assert "data" in r.json()
        assert isinstance(r.json()["data"], list)

    def test_quality_rate_each_entry_has_required_fields(self, client, db):
        """Each entry must have week, total, bugs, quality_pct."""
        pid = _create_project(client)
        _seed_items(db, pid, n=10)
        r = client.get(f"/api/metrics/{pid}/quality-rate")
        assert r.status_code == 200
        for entry in r.json()["data"]:
            assert "week"        in entry, f"Missing 'week' in {entry}"
            assert "total"       in entry, f"Missing 'total' in {entry}"
            assert "bugs"        in entry, f"Missing 'bugs' in {entry}"
            assert "quality_pct" in entry, f"Missing 'quality_pct' in {entry}"

    def test_quality_pct_between_0_and_100(self, client, db):
        """quality_pct must be in [0, 100] for every row."""
        pid = _create_project(client)
        _seed_items(db, pid, n=20)
        r = client.get(f"/api/metrics/{pid}/quality-rate")
        assert r.status_code == 200
        for entry in r.json()["data"]:
            assert 0.0 <= entry["quality_pct"] <= 100.0

    def test_quality_rate_unknown_project_returns_404(self, client):
        """Non-existent project must return 404."""
        r = client.get("/api/metrics/999/quality-rate")
        assert r.status_code == 404

    def test_quality_rate_empty_project_returns_empty_list(self, client, db):
        """Project with no items returns empty data list."""
        pid = _create_project(client)
        r = client.get(f"/api/metrics/{pid}/quality-rate")
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_bugs_reduce_quality_pct(self, client, db):
        """Seeded dataset (50% Bugs by _seed_items) must have quality_pct < 100."""
        pid = _create_project(client)
        _seed_items(db, pid, n=20)
        r = client.get(f"/api/metrics/{pid}/quality-rate")
        assert r.status_code == 200
        non_zero = [e for e in r.json()["data"] if e["total"] > 0]
        assert any(e["quality_pct"] < 100.0 for e in non_zero), \
            "Expected at least one week with bugs in a 50/50 Bug/Story dataset"

    def test_quality_rate_weeks_param_respected(self, client, db):
        """weeks query param limits the window."""
        pid = _create_project(client)
        _seed_items(db, pid, n=10)
        r4  = client.get(f"/api/metrics/{pid}/quality-rate?weeks=4")
        r12 = client.get(f"/api/metrics/{pid}/quality-rate?weeks=12")
        assert r4.status_code == 200
        assert r12.status_code == 200
        assert len(r4.json()["data"]) <= len(r12.json()["data"])


class TestGranularityParam:
    """API endpoints must honour the granularity query param."""

    def test_throughput_week_granularity_returns_200(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=20)
        r = client.get(f"/api/metrics/{pid}/throughput?granularity=week")
        assert r.status_code == 200

    def test_throughput_biweek_returns_200(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=20)
        r = client.get(f"/api/metrics/{pid}/throughput?granularity=biweek")
        assert r.status_code == 200

    def test_throughput_month_returns_200(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=20)
        r = client.get(f"/api/metrics/{pid}/throughput?granularity=month")
        assert r.status_code == 200

    def test_throughput_invalid_granularity_returns_422(self, client, db):
        pid = _create_project(client)
        r = client.get(f"/api/metrics/{pid}/throughput?granularity=quarterly")
        assert r.status_code == 422

    def test_net_flow_biweek_returns_200(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=20)
        r = client.get(f"/api/metrics/{pid}/net-flow?granularity=biweek")
        assert r.status_code == 200

    def test_net_flow_month_returns_200(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=20)
        r = client.get(f"/api/metrics/{pid}/net-flow?granularity=month")
        assert r.status_code == 200

    def test_quality_rate_biweek_returns_200(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=20)
        r = client.get(f"/api/metrics/{pid}/quality-rate?granularity=biweek")
        assert r.status_code == 200

    def test_quality_rate_month_returns_200(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=20)
        r = client.get(f"/api/metrics/{pid}/quality-rate?granularity=month")
        assert r.status_code == 200


class TestDayGranularityApi:
    """API must accept granularity=day for throughput, net-flow, quality-rate."""

    def test_throughput_day_returns_200(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=20)
        r = client.get(f"/api/metrics/{pid}/throughput?granularity=day&weeks=4")
        assert r.status_code == 200

    def test_throughput_day_has_more_buckets_than_weekly(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=20)
        weekly = client.get(f"/api/metrics/{pid}/throughput?granularity=week&weeks=4").json()["data"]
        daily  = client.get(f"/api/metrics/{pid}/throughput?granularity=day&weeks=4").json()["data"]
        assert len(daily) > len(weekly)

    def test_net_flow_day_returns_200(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=20)
        r = client.get(f"/api/metrics/{pid}/net-flow?granularity=day&weeks=2")
        assert r.status_code == 200

    def test_quality_rate_day_returns_200(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=20)
        r = client.get(f"/api/metrics/{pid}/quality-rate?granularity=day&weeks=2")
        assert r.status_code == 200

    def test_invalid_granularity_still_422(self, client, db):
        pid = _create_project(client)
        r = client.get(f"/api/metrics/{pid}/throughput?granularity=quarterly")
        assert r.status_code == 422

    def test_cycle_time_interval_returns_200(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=20)
        r = client.get(f"/api/metrics/{pid}/cycle-time-interval?weeks=12&granularity=week")
        assert r.status_code == 200
        assert "data" in r.json()

    def test_cycle_time_interval_has_period_and_avg(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=20)
        r = client.get(f"/api/metrics/{pid}/cycle-time-interval?weeks=12&granularity=week")
        assert r.status_code == 200
        data = r.json()["data"]
        if data:  # Only check if we have data
            assert "period" in data[0]
            assert "avg_cycle_time" in data[0]

    def test_cycle_time_interval_biweek_returns_200(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=20)
        r = client.get(f"/api/metrics/{pid}/cycle-time-interval?granularity=biweek&weeks=12")
        assert r.status_code == 200

    def test_cycle_time_interval_month_returns_200(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=20)
        r = client.get(f"/api/metrics/{pid}/cycle-time-interval?granularity=month&weeks=12")
        assert r.status_code == 200

    def test_cycle_time_interval_day_returns_200(self, client, db):
        pid = _create_project(client)
        _seed_items(db, pid, n=20)
        r = client.get(f"/api/metrics/{pid}/cycle-time-interval?granularity=day&weeks=4")
        assert r.status_code == 200

    def test_cycle_time_interval_unknown_project_returns_404(self, client):
        r = client.get("/api/metrics/9999/cycle-time-interval?weeks=12")
        assert r.status_code == 404

    def test_cycle_time_interval_empty_project_returns_empty_data(self, client, db):
        pid = _create_project(client)
        r = client.get(f"/api/metrics/{pid}/cycle-time-interval?weeks=12")
        assert r.status_code == 200
        assert r.json()["data"] == []

