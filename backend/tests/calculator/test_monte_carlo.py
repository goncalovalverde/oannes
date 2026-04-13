"""Unit tests for Monte Carlo simulation engine."""
import pytest
import re
from calculator.monte_carlo import simulate_when_done, simulate_how_many


SAMPLE_THROUGHPUT = [3, 5, 4, 6, 3, 5, 4, 5, 6, 4, 3, 5]  # 12 weeks of history
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class TestSimulateWhenDone:
    def test_returns_expected_keys(self):
        result = simulate_when_done(SAMPLE_THROUGHPUT, backlog_size=20)
        assert "percentiles" in result
        assert "histogram" in result
        assert "recommended_date" in result

    def test_percentiles_are_date_strings(self):
        result = simulate_when_done(SAMPLE_THROUGHPUT, backlog_size=20)
        for key in ("50", "70", "85", "95"):
            assert key in result["percentiles"]
            date_val = result["percentiles"][key]
            assert date_val is not None, f"percentile {key} is None"
            assert DATE_RE.match(date_val), f"percentile {key}={date_val!r} is not a date"

    def test_recommended_date_equals_p85(self):
        result = simulate_when_done(SAMPLE_THROUGHPUT, backlog_size=20)
        assert result["recommended_date"] == result["percentiles"]["85"]

    def test_percentile_date_ordering(self):
        """p50 date <= p70 date <= p85 date <= p95 date."""
        result = simulate_when_done(SAMPLE_THROUGHPUT, backlog_size=20)
        dates = [result["percentiles"][k] for k in ("50", "70", "85", "95")]
        assert dates == sorted(dates), f"Percentile dates not ordered: {dates}"

    def test_histogram_entries_have_required_fields(self):
        result = simulate_when_done(SAMPLE_THROUGHPUT, backlog_size=20)
        assert len(result["histogram"]) > 0
        entry = result["histogram"][0]
        assert "weeks" in entry
        assert "probability" in entry
        assert "cumulative" in entry

    def test_histogram_probabilities_sum_to_1(self):
        result = simulate_when_done(SAMPLE_THROUGHPUT, backlog_size=20)
        total_prob = sum(e["probability"] for e in result["histogram"])
        assert abs(total_prob - 1.0) < 0.02, f"Histogram probs sum to {total_prob}"

    def test_zero_or_negative_backlog_returns_nulls(self):
        result = simulate_when_done(SAMPLE_THROUGHPUT, backlog_size=0)
        assert result["percentiles"]["50"] is None

    def test_empty_throughput_returns_nulls(self):
        result = simulate_when_done([], backlog_size=10)
        assert result["percentiles"]["50"] is None

    def test_deterministic_output(self):
        """Explicit seed produces identical output across runs."""
        r1 = simulate_when_done(SAMPLE_THROUGHPUT, backlog_size=15, seed=42)
        r2 = simulate_when_done(SAMPLE_THROUGHPUT, backlog_size=15, seed=42)
        assert r1["percentiles"]["85"] == r2["percentiles"]["85"]

    def test_larger_backlog_gives_later_dates(self):
        small = simulate_when_done(SAMPLE_THROUGHPUT, backlog_size=10)
        large = simulate_when_done(SAMPLE_THROUGHPUT, backlog_size=100)
        assert large["percentiles"]["50"] > small["percentiles"]["50"]


class TestSimulateHowMany:
    def test_returns_expected_keys(self):
        result = simulate_how_many(SAMPLE_THROUGHPUT, weeks=4)
        assert "percentiles" in result
        assert "histogram" in result

    def test_percentile_keys_present(self):
        result = simulate_how_many(SAMPLE_THROUGHPUT, weeks=4)
        for key in ("50", "70", "85", "95"):
            assert key in result["percentiles"]

    def test_percentile_ordering(self):
        result = simulate_how_many(SAMPLE_THROUGHPUT, weeks=4)
        vals = [result["percentiles"][k] for k in ("50", "70", "85", "95")]
        assert vals == sorted(vals), f"Percentile values not ordered: {vals}"

    def test_p50_is_reasonable(self):
        """With avg ~4.5/week for 4 weeks, median should be ~14-22."""
        result = simulate_how_many(SAMPLE_THROUGHPUT, weeks=4)
        assert 10 <= result["percentiles"]["50"] <= 30, f"Unexpected p50={result['percentiles']['50']}"

    def test_more_weeks_means_more_items(self):
        short = simulate_how_many(SAMPLE_THROUGHPUT, weeks=2)
        long  = simulate_how_many(SAMPLE_THROUGHPUT, weeks=8)
        assert long["percentiles"]["50"] > short["percentiles"]["50"]

    def test_histogram_entries_have_required_fields(self):
        result = simulate_how_many(SAMPLE_THROUGHPUT, weeks=4)
        assert len(result["histogram"]) > 0
        entry = result["histogram"][0]
        assert "items" in entry
        assert "probability" in entry
        assert "cumulative" in entry

    def test_histogram_probabilities_sum_to_1(self):
        result = simulate_how_many(SAMPLE_THROUGHPUT, weeks=4)
        total_prob = sum(e["probability"] for e in result["histogram"])
        assert abs(total_prob - 1.0) < 0.02

    def test_deterministic_output(self):
        """Explicit seed produces identical output across runs."""
        r1 = simulate_how_many(SAMPLE_THROUGHPUT, weeks=4, seed=42)
        r2 = simulate_how_many(SAMPLE_THROUGHPUT, weeks=4, seed=42)
        assert r1["percentiles"]["50"] == r2["percentiles"]["50"]

    def test_zero_weeks_returns_nulls(self):
        result = simulate_how_many(SAMPLE_THROUGHPUT, weeks=0)
        assert result["percentiles"]["50"] is None

    def test_empty_throughput_returns_nulls(self):
        result = simulate_how_many([], weeks=4)
        assert result["percentiles"]["50"] is None

